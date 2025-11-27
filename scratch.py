import tiktoken

encoding = tiktoken.get_encoding('cl100k_base')

print(len(encoding.encode("Hello world")))