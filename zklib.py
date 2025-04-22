from zk import ZK

# Connect to the MB40 device
zk = ZK('192.168.1.71', port=4370, timeout=5)
conn = zk.connect()

# Fetch user by PIN
user = conn.get_user(uid=650002)  # or conn.get_users() for all users
if user:
    print(f"Name: {user.name}")
    print(f"Card Number: {user.cardno}")

conn.disconnect()