import json
import logging
import os
import re
import requests
from typing import Optional

import pandas as pd

from archytas.tool_utils import tool, toolset, AgentRef, LoopControllerRef

logging.disable(logging.WARNING)  # Disable warnings
logger = logging.Logger(__name__)


@toolset()
class DatasetToolset:
    """ """

    dataset_id: Optional[int]
    df: Optional[pd.DataFrame]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset()

    def set_dataset(self, dataset_id, agent=None):
        self.dataset_id = dataset_id
        meta_url = f"{os.environ['DATA_SERVICE_URL']}/datasets/{self.dataset_id}"
        self.dataset = requests.get(meta_url).json()
        if self.dataset:
            self.load_dataframe()
        else:
            raise Exception(f"Dataset '{dataset_id}' not found.")

    def load_dataframe(self, filename=None):
        if filename is None:
            filename = self.dataset.get('file_names', [])[0]
        meta_url = f"{os.environ['DATA_SERVICE_URL']}/datasets/{self.dataset_id}"
        data_url_req = requests.get(f'{meta_url}/download-url?filename={filename}')
        data_url = data_url_req.json().get('url', None)
        if data_url is not None:
            self.df = pd.read_csv(data_url)
        else:
            raise Exception('Unable to open dataset.')

    def reset(self):
        self.dataset_id = None
        self.df = None

    def send_dataset(self):
        pass

    def context(self):
        return f"""You are an analyst whose goal is to help with scientific data analysis and manipulation in Python.

You are working on a dataset named: {self.dataset.get('name')}

The description of the dataset is:
{self.dataset.get('description')}

The dataset has the following structure:
--- START ---
{self.dataset_info()}
--- END ---

Please answer any user queries to the best of your ability, but do not guess if you are not sure of an answer.
If you are asked to manipulate or visualize the dataset, use the generate_python_code tool.
"""

    @tool()
    def dataset_info(self) -> str:
        """
        Inspect the dataset and return information and metadata about it.

        This should be used to answer questions about the dataset, including information about the columns,
        and default parameter values and initial states.


        Returns:
            str: a textual representation of the dataset
        """
        # Update the local dataframe to match what's in the shell.
        # This will be factored out when we switch around to allow using multiple runtimes.
        try:
            self.df = self.kernel.ev("df")
        except:
            pass

        output = f"""
Dataframe head:
{self.df.head(15)}


Columns:
{self.df.columns}


dtypes:
{self.df.dtypes}


Statistics:
{self.df.describe()}
"""
        return output

    @tool()
    def generate_python_code(
        self, query: str, agent: AgentRef, loop: LoopControllerRef
    ) -> str:
        """
        Generated Python code to be run in an interactive Jupyter notebook for the purpose of exploring, modifying and visualizing a Pandas Dataframe.

        Input is a full grammatically correct question about or request for an action to be performed on the loaded dataframe.

        Assume that the dataframe is already loaded and has the variable name `df`.
        Information about the dataframe can be loaded with the `dataset_info` tool.

        Args:
            query (str): A fully grammatically correct queistion about the current dataset.

        Returns:
            str: A LLM prompt that should be passed evaluated.
        """
        # set up the agent
        # str: Valid and correct python code that fulfills the user's request.
        prompt = f"""
You are a programmer writing code to help with scientific data analysis and manipulation in Python.

Please write code that satisfies the user's request below.

You have access to a variable name `df` that is a Pandas Dataframe with the following structure:
{self.dataset_info()}

If you are asked to modify or update the dataframe, modify the dataframe in place, keeping the updated variable to still be named `df`.

You also have access to the libraries pandas, numpy, scipy, matplotlib.

Please generate the code as if you were programming inside a Jupyter Notebook and the code is to be executed inside a cell.
You MUST wrap the code with a line containing three backticks (```) before and after the generated code.
No addtional text is needed in the response, just the code block.
"""

        llm_response = agent.oneshot(prompt=prompt, query=query)
        loop.set_state(loop.STOP_SUCCESS)
        preamble, code, coda = re.split("```\w*", llm_response)
        result = json.dumps(
            {
                "action": "code_cell",
                "language": "python",
                "content": code.strip(),
            }
        )
        return result
