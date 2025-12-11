
from datasets import load_dataset

# Load the dataset
# subset: ljp_criminal
ds = load_dataset("lbox/lbox_open", "ljp_criminal", split="train", trust_remote_code=True)

# Get row 83
row_83 = ds[83]
print("=== ROW 83 REASON ===")
print(row_83.get('reason', 'No reason column found'))

# Get a few others to see patterns
print("\n=== ROW 0 REASON ===")
print(ds[0].get('reason', 'No reason column found'))

print("\n=== ROW 10 REASON ===")
print(ds[10].get('reason', 'No reason column found'))
