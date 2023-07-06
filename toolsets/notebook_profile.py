import json
from rich import print, traceback; traceback.install(show_locals=True)

import pdb


#TODO: captioning images/generated plots
# from transformers import pipeline
# captioner = pipeline("image-to-text",model="Salesforce/blip-image-captioning-base")
# captioner("https://huggingface.co/datasets/Narsil/image_dummy/raw/main/parrots.png")
# ## [{'generated_text': 'two birds are standing next to each other '}]


"""
strip out just the query and the generated code
run the sequence through the llm, ask it to write a summary of what the code does
- query
- thoughts.thought
- thoughts.tool
- cell.source

TBD how to look at the output

data[i]['query'|'thought']
data[i]['cell'][cell_type='code' & (source|outputs)]


"""

from archytas.agent import Agent, Message, Role


def main():
    # Load your JSON file
    with open('nb.json', 'r') as f:
        data = json.load(f)

    # Run the profile_notebook function
    summary = profile_notebook(data)
    print(summary)


def profile_notebook(data:dict, debug:bool=True):

    # make an agent
    agent = Agent(prompt='You are an automatic code notebook summarizer. Code comes from an interactive environment where a user and AI systems collaborate on a task. The following sequence was extracted from a notebook.')
    
    # add the data from each cell to the agent's chat history
    for cell in data:
        line = f"""
user query: {cell['query']}
AI thought: {cell['thoughts']['thought']}
generated code:

```python
{cell['cell']['source']}
```
""".strip()
        agent.add_context(line)
        
        if debug:
            print(line)
            print('-'*80)

    # generate the summary
    summary = agent.query('Please provide a 1-2 sentence high level summary of the notebook and what it accomplishes. Be sure to pay attention to what the code actually does, not just what the user requested or what the comments say, and note any discrepancies. Also do not speculate beyond what is in the notebook.')
    
    return summary



if __name__ == '__main__':
    main()











