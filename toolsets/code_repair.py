from archytas.agent import Agent

from textwrap import dedent, indent
import re


def code_repair(agent:Agent, code:str, error:str, language:str, fix_section:slice=None, description:str=None) -> str:
    """
    Attempt to fix broken code. Provide the code, the error, and an optional description of what the code is trying to accomplish. This tool will attempt to rewrite the code to fix the error.

    Args:
        code (str): The code containing an issue to be fixed
        error (str): The error that is occurring. This can be a stack trace or a verbal description of the error.
        language (str): The language the code is written in. Should be a valid language name such as 'python', 'rust', 'haskell', etc.
        fix_section (slice, optional): Indicates which portion of the code should be replaced by a fix. Defaults to None, which means the entire code will be replaced.
        description (str, optional): A description of what the code is trying to accomplish. Defaults to None.

    Returns:
        str: The fixed code

    """
    prompt = f"You are an experienced {language} developer."
    
    query = f"""
The following code is broken:

```{language}
{dedent(code)}
```

Here is the issue:

{dedent(error)}
"""

    if description is not None:
        query += f"""

Here is a description of the code:
{indent(dedent(description), '    ')}
"""

    if fix_section is not None:
        query += f"""

Please fix just the following section of code:
```{language}
{dedent(code[fix_section])}
```
"""
    else:
        query += f"""

Please generate a new version of the code that fixes the issue.
"""

    query += f"""

Please include only one code block in your response. Do not write any other code in your output, only write the code that fixes the issue.
"""

    res = agent.oneshot(prompt=prompt, query=query)

    # extract the code block from the result
    # This will break if the llm outputted more than one code block
    pattern = r"^```" + language + r"[\n].*[\n]```$"
    match = re.search(pattern, res, re.MULTILINE | re.DOTALL)
    if match is None:
        raise Exception(f"Could not find a code block in the result. Full result:\n{res}")
    
    code_block = match.group(0)

    # strip the code block markers
    code_block = code_block[len(f'```{language}\n'):-len('```')]

    return code_block



def main():
    from dataclasses import dataclass
    @dataclass
    class BrokenCode:
        code:str
        error:str
        language:str
        fix_section:slice=None
        description:str=None

    from archytas.react import ReActAgent

    agent = ReActAgent()

    examples = [
        BrokenCode(
            code = """
def get_sum_of_list(lst):
    sum = 0
    for item in lst:
        sum += item
    return sum

my_list = [1, 2, '3', 4, 5]
print(get_sum_of_list(my_list))
""".strip(),
            error = """
Traceback (most recent call last):
  File "/home/david/dev/archytas/archytas/test1.py", line 8, in <module>
    print(get_sum_of_list(my_list))
  File "/home/david/dev/archytas/archytas/test1.py", line 4, in get_sum_of_list
    sum += item
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
""".strip(),
            language = 'python',
            description = """This function aims to calculate the sum of all elements in a list and print it.""",
        ),

        BrokenCode(
            code = """
def fetch_item(dictionary, key):
    return dictionary[key]

data = {'name': 'John', 'age': 30}
print(fetch_item(data, 'city'))
""".strip(),
            error = """
Traceback (most recent call last):
  File "/home/david/dev/archytas/archytas/test1.py", line 5, in <module>
    print(fetch_item(data, 'city'))
  File "/home/david/dev/archytas/archytas/test1.py", line 2, in fetch_item
    return dictionary[key]
KeyError: 'city'
""".strip(),
            language = 'python',
            description = """The goal of this code is to extract a particular piece of information from a dictionary using a key, and print the retrieved value."""
        ),

        BrokenCode(
            code = """
import numpy as np

a = np.array([1, 2, 3])
b = np.array([4, 5])

print(np.dot(a, b))
""".strip(),
            error = """
File "/home/david/dev/archytas/archytas/test1.py", line 6, in <module>
    print(np.dot(a, b))
  File "<__array_function__ internals>", line 200, in dot
ValueError: shapes (3,) and (2,) not aligned: 3 (dim 0) != 2 (dim 0)
""".strip(),
            language = 'python',
            description = """The objective of this piece of code is to perform a dot product operation on two numerical arrays using a popular scientific computing library in Python, numpy."""
        ),

        BrokenCode(
            code = """
def recursive_function(n):
    if n == 0:
        return 1
    else:
        return n * recursive_function(n)

recursive_function(5)
""".strip(),
            error = """
Traceback (most recent call last):
  File "/home/david/dev/archytas/archytas/test1.py", line 7, in <module>
    recursive_function(5)
  File "/home/david/dev/archytas/archytas/test1.py", line 5, in recursive_function
    return n * recursive_function(n)
  File "/home/david/dev/archytas/archytas/test1.py", line 5, in recursive_function
    return n * recursive_function(n)
  File "/home/david/dev/archytas/archytas/test1.py", line 5, in recursive_function
    return n * recursive_function(n)
  [Previous line repeated 995 more times]
  File "/home/david/dev/archytas/archytas/test1.py", line 2, in recursive_function
    if n == 0:
RecursionError: maximum recursion depth exceeded in comparison
""".strip(),
            language = 'python',
            description = """This code is an attempt to implement a function that performs a calculation involving recursion, with a specific base case defined for when the input is 0."""
        ),
]

    for example in examples:
        print(f"Original code:\n```{example.language}\n{example.code}\n```\n")
        print(f"Error:\n{example.error}\n")
        repaired = code_repair(agent, example.code, example.error, example.language, fix_section=example.fix_section, description=example.description)
        print(f"Repaired code:\n```{example.language}\n{repaired}\n```\n")


    


if __name__ == '__main__':
    main()