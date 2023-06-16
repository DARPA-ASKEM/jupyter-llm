// @ts-nocheck
// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

import { PageConfig, URLExt } from '@jupyterlab/coreutils';
(window as any).__webpack_public_path__ = URLExt.join(
  PageConfig.getBaseUrl(),
  'example/'
);

import '@jupyterlab/application/style/index.css';
import '@jupyterlab/codemirror/style/index.css';
import '@jupyterlab/completer/style/index.css';
import '@jupyterlab/documentsearch/style/index.css';
import '@jupyterlab/notebook/style/index.css';
import '@jupyterlab/theme-light-extension/style/theme.css';
import '../index.css';

import { CommandRegistry } from '@lumino/commands';

import { CommandPalette, SplitPanel, Widget } from '@lumino/widgets';

import { ServiceManager } from '@jupyterlab/services';
import { MathJaxTypesetter } from '@jupyterlab/mathjax2';

import {
  NotebookModelFactory,
  NotebookPanel,
  NotebookWidgetFactory
} from '@jupyterlab/notebook';

import {
  Completer,
  CompleterModel,
  CompletionHandler,
  KernelConnector
} from '@jupyterlab/completer';
import { createMessage } from '@jupyterlab/services/lib/kernel/messages';
import { IKernelConnection } from '@jupyterlab/services/lib/kernel/kernel';

import { editorServices } from '@jupyterlab/codemirror';

import { DocumentManager } from '@jupyterlab/docmanager';

import { DocumentRegistry } from '@jupyterlab/docregistry';

import {
  standardRendererFactories as initialFactories,
  RenderMimeRegistry
} from '@jupyterlab/rendermime';
import { SetupCommands } from './commands';

function main(): void {
  const manager = new ServiceManager();
  void manager.ready.then(() => {
    createApp(manager);
  });
}

function createApp(manager: ServiceManager.IManager): void {
  // Initialize the command registry with the bindings.
  const commands = new CommandRegistry();
  const useCapture = true;

  // Setup the keydown listener for the document.
  document.addEventListener(
    'keydown',
    event => {
      commands.processKeydownEvent(event);
    },
    useCapture
  );

  const rendermime = new RenderMimeRegistry({
    initialFactories: initialFactories,
    latexTypesetter: new MathJaxTypesetter({
      url: PageConfig.getOption('mathjaxUrl'),
      config: PageConfig.getOption('mathjaxConfig')
    })
  });

  const opener = {
    open: (widget: Widget) => {
      // Do nothing for sibling widgets for now.
    }
  };

  const docRegistry = new DocumentRegistry();
  const docManager = new DocumentManager({
    registry: docRegistry,
    manager,
    opener
  });
  const mFactory = new NotebookModelFactory({});
  const editorFactory = editorServices.factoryService.newInlineEditor;
  const contentFactory = new NotebookPanel.ContentFactory({ editorFactory });

  const wFactory = new NotebookWidgetFactory({
    name: 'Notebook',
    modelName: 'notebook',
    fileTypes: ['notebook'],
    defaultFor: ['notebook'],
    preferKernel: true,
    canStartKernel: true,
    rendermime,
    contentFactory,
    mimeTypeService: editorServices.mimeTypeService
  });
  docRegistry.addModelFactory(mFactory);
  docRegistry.addWidgetFactory(wFactory);

  const notebookPath = PageConfig.getOption('notebookPath');
  const nbWidget = docManager.open(notebookPath) as NotebookPanel;

  const editor =
    nbWidget.content.activeCell && nbWidget.content.activeCell.editor;
  const model = new CompleterModel();
  const completer = new Completer({ editor, model });
  const sessionContext = nbWidget.context.sessionContext;
  const connector = new KernelConnector({
    session: sessionContext.session
  });
  const handler = new CompletionHandler({ completer, connector });

  void sessionContext.ready.then(() => {
    handler.connector = new KernelConnector({
      session: sessionContext.session
    });
  });

  console.log(nbWidget);
  console.log(wFactory);
  console.log(docManager);
  console.log(model);

  const handleMessage = (contex, msg) => {
    if (msg.msg_type === "status") {
      return;
    }
    else if (msg.msg_type === "stream") {
      // console.log("Possible LLM Thought: ", msg.content.text);
      // console.log(nbWidget);
      nbWidget.content.model.cells.nbmodel.addCell({id: `${msg.id}-text`, cell_type: 'markdown', source: msg.content.text})
    }
    else if (msg.msg_type === "llm_response") {
      const text = msg.content.text;
      // alert(text)
      nbWidget.content.model.cells.nbmodel.addCell({id: `${msg.id}-text`, cell_type: 'markdown', source: msg.content.text})
    }
    else if (msg.msg_type === "code_cell") {
      console.log(msg);
    }
  }

  void sessionContext.ready.then(() => {
    const session = sessionContext.session;
    // const kernel = session?.kernel;
    session?.iopubMessage.connect(handleMessage);
  });

  // Set the handler's editor.
  handler.editor = editor;

  // Listen for active cell changes.
  nbWidget.content.activeCellChanged.connect((sender, cell) => {
    handler.editor = cell && cell.editor;
  });

  // Hide the widget when it first loads.
  completer.hide();

  const setKernelContext = (kernel: IKernelConnection, context_info) => {
    const messageBody = {
      session: props.llmContext.session?.name || '',
      channel: 'shell',
      content: context_info,
      msgType: 'context_setup_request',
      msgId: `${kernel.id}-setcontext`
    };
    const message: JupyterMessage = createMessage(messageBody);
    kernel?.sendShellMessage(message);
    // kernelState.value = KernelState.busy;
  };


  const sendLLMQuery = (query: string) => {
    const session = sessionContext.session;
    const kernel = session?.kernel;
    if (kernel) {
      const message: JupyterMessage = createMessage({
        session: session?.name || '',
        channel: 'shell',
        content: { request: query },
        msgType: 'llm_request',
        msgId: `${kernel.id}-setcontext`
      });
      kernel.sendShellMessage(message);
    }

  };

  const llmWidget = new Widget();
  const llmNode = document.createElement('input')
  llmNode.placeholder = 'Enter LLM query:';
  llmNode.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      sendLLMQuery(llmNode.value);
    }
  }, false);
  llmWidget.node.appendChild(llmNode);


  const panel = new SplitPanel();
  panel.id = 'main';
  panel.orientation = 'horizontal';
  panel.spacing = 0;
  SplitPanel.setStretch(llmWidget, 1);
  SplitPanel.setStretch(nbWidget, 2);
  panel.addWidget(llmWidget);
  panel.addWidget(nbWidget);

  // Attach the panel to the DOM.
  Widget.attach(panel, document.body);
  Widget.attach(completer, document.body);

  // Handle resize events.
  window.addEventListener('resize', () => {
    panel.update();
  });

  SetupCommands(commands, nbWidget, handler);

  console.debug('Example started!');
}

window.addEventListener('load', main);
