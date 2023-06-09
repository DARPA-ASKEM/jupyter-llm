# Jupyter package

This package provides a custom Jupyter kernel for the ASKEM project that allows extra communication beyond the usual Jupyter message types to allow for the kernel to interact with an LLM (GPT-4) and answer questions and generate code that is runnable in native notebook code cells.

The kernel connects to the Terarium Data Service to allow contextual queries about Terarium assets such as visualizing or modifying datasets.


This package contains 4 different products:

* A Python module named `jupyter_llm` (`pyproject.toml`)
* A Jupyter kernel (`llmkernel`)
* A Jupyter service (`main.py`)
* A standalone development interface (`dev_ui`)

## Install / setup

### jupyter_llm Python module

Normal installation:
```bash
# Requires poetry
$ poetry install
```

Global installation (e.g. Docker):
```bash
$ poetry config virtualenvs.create false
$ poetry install --no-dev
```

### Jupyter kernel

To install the kernel, simply copy or symlink the `llmkernel` directory in to one of the directories defined in the following document:

https://jupyter-client.readthedocs.io/en/stable/kernels.html#kernel-specs


For example:
```bash
$ cp -r llmkernel /usr/share/jupyter/kernels/llmkernel
```

Once the directory exists and the jupyter service is restarted the kernel should be available for selection.

For development, the kernel is automatically installed in the proper location in your development virtual environment when you run `make dev-install` as explained in the Dev setup section.


## Dev setup

This package is bundled with a basic development UI for development and testing.

To get started run this command:

```bash
$ make dev-install
```

This will copy install all of the prerequisites.

You will need to update the .env file with your OpenAI/GPT API key to use the LLM. To connect to the data service, you will need to update the .env file with the url of a running instance.

Once you have set up the environment and added your keys you can start the dev server by running:

```bash
$ make dev
```

This will start the Jupyter service and launch a specialized notebook interface in your browser similar to if you ran `$ jupyter notebook` normally.


### LLM flow

