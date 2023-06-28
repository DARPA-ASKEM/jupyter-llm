import ast
import asyncio
import os
import pickle
import sys
import time
import json
import requests
import traceback
import uuid

from tornado import ioloop
from jupyter_kernel_proxy import KernelProxyManager, JupyterMessage, InterceptionFilter, KERNEL_SOCKETS, KERNEL_SOCKETS_NAMES
from jupyter_core.paths import jupyter_runtime_dir, jupyter_data_dir
from toolsets.dataset_toolset import DatasetToolset
from archytas.react import ReActAgent

PROXIED_KERNEL_ID = None
server_url = os.environ.get("JUPYTER_SERVER", None)
server_token = os.environ.get("JUPYTER_TOKEN", None)

class PythonLLMKernel(KernelProxyManager):
    implementation = "askem-chatty-py"
    implementation_version = "0.1"
    banner = "Chatty ASKEM"

    language_info = {
        "mimetype": "text/plain",
        "name": "text",
        "file_extension": ".txt",
    }

    def __init__(self, server):
        super().__init__(server)
        self.new_kernel()
        self.setup_instance()

    def setup_instance(self):
        # Init LLM agent
        print("Initializing LLM")
        self.toolset = DatasetToolset()
        self.agent = ReActAgent(tools=[self.toolset], allow_ask_user=False, verbose=True, spinner=None, rich_print=False)
        self.toolset.agent = self.agent
        if getattr(self, 'context', None) is not None:
            self.agent.clear_all_context()
        self.context = None
        self.server.intercept_message("shell", "context_setup_request", self.context_setup_request)
        self.server.intercept_message("shell", "llm_request", self.llm_request)

    def connect_to_last(self):
        # We don't want to automatically connect to the last kernel
        return
    
    def new_kernel(self):
        if PROXIED_KERNEL_ID is not None:
            # We should destroy any existing sub-kernel before creating a new one
            del_res = requests.delete(f"{server_url}/api/kernels/{PROXIED_KERNEL_ID}", headers={"Authorization": f"token {server_token}"})
            print(del_res.status_code)
            print(del_res.json())

        # TODO: Replace hard coded python3
        res = requests.post(f"{server_url}/api/kernels", json={"name": "python3", "path": ""}, headers={"Authorization": f"token {server_token}"})
        kernel_info = res.json()
        self.update_running_kernels()
        sub_kernel = kernel_info['id']
        PROXIED_KERNEL_ID = sub_kernel
        self.connect_to(sub_kernel)

    async def execute(self, command, response_handler=None, collect_output=True):
        # print(f"self.response_data: '{getattr(self, 'response_data', None)}'")
        stream = self.connected_kernel.streams.shell
        execution_message = self.connected_kernel.make_multipart_message(
            msg_type="execute_request", 
            content={
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": True,
                "stop_on_error": False,
                "code": command,
            }, 
            parent_header={},
            metadata={
                "trusted": True,
            }
        )
        stream.send_multipart(execution_message)
        message_id = JupyterMessage.parse(execution_message).header.get("msg_id")


        message_context = {
            "id": message_id,
            "stdout_list": [],
            "stderr_list": [],
            "return": None,
            "error": None,
            "done": False,
            "result": None,
        }

        filter_list = self.server.filters

        shell_socket = KERNEL_SOCKETS[KERNEL_SOCKETS_NAMES.index("shell")]
        iopub_socket = KERNEL_SOCKETS[KERNEL_SOCKETS_NAMES.index("iopub")]


        # Generate a handler to catch and silence the output
        async def silence_message(server, target_stream, data):
            message = JupyterMessage.parse(data)

            filter_list.remove(InterceptionFilter(iopub_socket, "execute_input", silence_message))
            filter_list.remove(InterceptionFilter(iopub_socket, "execute_request", silence_message))

            if message.parent_header.get("msg_id", None) != message_id:
                return data
            return None


        async def collect_result(server, target_stream, data):
            message = JupyterMessage.parse(data)
            # Ensure we are only working on handlers for this message response
            if message.parent_header.get("msg_id", None) != message_id:
                return data
            
            data = message.content["data"].get("text/plain", None)
            message_context["return"] = data


        async def collect_stream(server, target_stream, data):
            message = JupyterMessage.parse(data)
            # Ensure we are only working on handlers for this message response
            if message.parent_header.get("msg_id", None) != message_id:
                return data
            stream = message.content["name"]
            message_context[f"{stream}_list"].append(message.content["text"])


        async def cleanup(server, target_stream, data):
            message = JupyterMessage.parse(data)
            # Ensure we are only working on handlers for this message response
            if message.parent_header.get("msg_id", None) != message_id:
                return data
            if response_handler:
                filter_list.remove(InterceptionFilter(iopub_socket, "stream", response_handler))
            if collect_stream:
                filter_list.remove(InterceptionFilter(iopub_socket, "stream", collect_stream))
            filter_list.remove(InterceptionFilter(iopub_socket, "execute_result", collect_result))
            filter_list.remove(InterceptionFilter(shell_socket, "execute_reply", cleanup))
            message_context["result"] = message
            message_context["done"] = True


        filter_list.append(InterceptionFilter(iopub_socket, "execute_input", silence_message))
        filter_list.append(InterceptionFilter(iopub_socket, "execute_request", silence_message))
        filter_list.append(InterceptionFilter(iopub_socket, "execute_result", collect_result))
        filter_list.append(InterceptionFilter(shell_socket, "execute_reply", cleanup))
        if collect_stream:
            filter_list.append(InterceptionFilter(iopub_socket, "stream", collect_stream))

        if response_handler:
            filter_list.append(InterceptionFilter(iopub_socket, "stream", response_handler))
        
        await asyncio.sleep(0.1)
        while not message_context["done"]:
            await asyncio.sleep(1)
        return message_context


    async def evaluate(self, variable):
        result = await self.execute(variable, collect_output=True)
        return result
        

    async def set_context(self, context, context_info):
        print("set context")
        match context:
            case "dataset":
                dataset_id = context_info["id"]
                print(f"Processing dataset w/id {dataset_id}")
                self.toolset.set_dataset(dataset_id)
                self.context = self.agent.add_context(self.toolset.context())
                await self.execute('''import pandas as pd; import numpy as np; import scipy; import pickle; df = pickle.loads({}); print("done");'''.format(pickle.dumps(self.toolset.df)))
                await self.send_df_preview_message()


    async def send_df_preview_message(self):
        print("Sending preview")
        import pandas as pd
        result = await self.evaluate("pickle.dumps(df)")
        result_literal = ast.literal_eval(result["return"])
        # df = pd.read_json(result["return"])
        df = pickle.loads(result_literal)
        if isinstance(df, pd.DataFrame):
            split_df = json.loads(df.head(30).to_json(orient="split"))
            payload = {
                "name": "Temp dataset (not saved)",
                "headers": split_df["columns"],
                "csv": [split_df["columns"]] + split_df["data"],
            }
            self.send_response("iopub", "dataset", payload)


    def send_response(self, stream, msg_or_type, content=None, channel=None):
        # Parse response as needed
        stream = getattr(self.server.streams, stream)
        stream.send_multipart(self.server.make_multipart_message(msg_type=msg_or_type, content=content, parent_header={}))


    # async def llm_request(self, queue, message_id, message, **kwargs):
    async def llm_request(self, queue, message_id, message, **kwargs):
        # Send "code" to LLM Agent. The "code" is actually the LLM query
        message = JupyterMessage.parse(message)
        content = message.content
        request = content.get('request', None)
        if not request:
            return
        try:
            result = self.agent.react(request)
        except Exception as err:
            error_text = f"""LLM Error:
{err}

{traceback.format_exc()}
"""
            stream_content = {"name": "stderr", "text": error_text}
            self.send_response("iopub", "stream", stream_content)
            return {
                "status": "error",
                "execution_count": self.execution_count,
                "payload": [],
                'user_expressions': {},
            }

        try:
            data = json.loads(result)
            if isinstance(data, dict) and data.get("action") == "code_cell":
                stream_content = {"language": data.get("language"), "code": data.get("content")}
                self.send_response("iopub", "code_cell", stream_content)
        except json.JSONDecodeError:  # If response is not a json, it's just text so treat it like text
            stream_content = {"name": "response_text", "text": f"{result}"}
            self.send_response("iopub", "llm_response", stream_content)
        # return 

    # async def context_setup_request(self, queue, message_id, message, **kwargs):
    async def context_setup_request(self, server, target_stream, data):
        # TODO: Set up environment for kernel
        # Basically, run any code/import any files needed for context

        print("set context")
        message = JupyterMessage.parse(data)
        content = message.content
        context = content.get('context')
        context_info = content.get('context_info', {})

        if content:
            await self.set_context(context, context_info)

        self.send_response(
            stream="iopub",
            msg_or_type="status",
            content={
                "execution_state": "idle",
            },
            channel="iopub"

        )


def cleanup():

    pass

def start(connection_file):
    loop = ioloop.IOLoop.current()

    with open(connection_file) as f:
        notebook_config = json.load(f)

    proxy_manager = PythonLLMKernel(notebook_config)

    try:
        loop.start()
    except KeyboardInterrupt:
        # Perform shutdown cleanup here
        cleanup()
        sys.exit(0)


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "start":
        start(sys.argv[2])
    else:
        print("Usage: {:s} start <connection_file>".format(sys.argv[0]))

if __name__ == "__main__":
    asyncio.run(main())


