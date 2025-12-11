
from datasets import load_dataset

ds = load_dataset("lbox/lbox_open", "ljp_criminal", split="train", trust_remote_code=True)
row_83 = ds[83]['reason']

print(f"Has \\u3000: {'\u3000' in row_83}")
print(f"Has \\xa0: {'\xa0' in row_83}")
print(repr(row_83))
