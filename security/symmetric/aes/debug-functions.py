from aes128 import *
from Crypto.Cipher import AES


plaintext = b"HelloWorldGuys!!"
key_bytes = b"ThisIsAKeyGuys!!"

state = build_state(plaintext)
key = build_state(key_bytes)

print(flatten_state(state))

print("\nsubstitute_bytes:\n")

substitute_bytes(state)
print(flatten_state(state))

inverse_substitute_bytes(state)
print(flatten_state(state))

print("\nshift_rows:\n")

shift_rows(state)
print(flatten_state(state))

inverse_shift_rows(state)
print(flatten_state(state))

print("\nmix_columns:\n")

mix_columns(state)
print(flatten_state(state))

inverse_mix_columns(state)
print(flatten_state(state))

print("\nadd_round_key:\n")

add_round_key(key, state)
print(flatten_state(state))

add_round_key(key, state)
print(flatten_state(state))

print("\naes128_encrypt:\n")

ciphertext = aes128_encrypt(key_bytes, plaintext)
print(ciphertext)

cipher = AES.new(key_bytes, AES.MODE_ECB)
print(cipher.encrypt(plaintext), AES.block_size)

print("\naes128_decrypt:\n")

print(aes128_decrypt(key_bytes, ciphertext))
print(cipher.decrypt(cipher.encrypt(plaintext)), AES.block_size)