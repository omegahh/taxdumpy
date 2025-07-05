
b_str = lambda x: f"\033[1m{x}\033[0m" # Bold
u_str = lambda x: f"\033[1;4m{x}\033[0m"  # UnderLine
r_str = lambda x: f"\033[1;31m{x}\033[0m" # Red
m_color = lambda m: f"\033[1;31m{m.group(0)}\033[0m"
