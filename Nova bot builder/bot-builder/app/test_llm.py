from llm import llm


response = llm.invoke("سلام، فقط بگو اتصال موفق بود.")
print(response.content)