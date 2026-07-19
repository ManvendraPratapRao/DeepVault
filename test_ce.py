from sentence_transformers import CrossEncoder

encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
pairs = [["What is deepvault?", "Deepvault is a secure data storage."]]
res = encoder.predict(pairs)
print(type(res), res)
