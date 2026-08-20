from torch.cuda import is_available
import torch.version

print("cuda version >>", torch.version.cuda)
print(is_available())
