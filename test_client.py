import requests
import json
import time

# The API endpoint
url = "http://127.0.0.1:8000/merge"

# The data to be sent
data = {
  "videos": [
    "https://replicate.delivery/xezq/FsGObZ0yglIDDBaeJ1XN1GexStnk287bmdW7VVIg1ugf3VeSB/tmp3i3dt0j1.mp4",
    "https://replicate.delivery/xezq/nyvMkkeFbFT8Xq8W042Hv0X6BqeR8Iy873yiM16zDUpG8KvUA/tmpanvqcpo_.mp4",
    "https://replicate.delivery/xezq/0MeLyftUzcrcVkZATxLUm2q54TUgyqffocqLlmkpCsOkwr8SB/tmppzd4jnkc.mp4",
    "https://replicate.delivery/xezq/YFxQnjyMUIa7CJ1Bt7DAMefEtw0khGNBen3cs3N6Cm9D4VeSB/tmprmbbw8co.mp4",
    "https://replicate.delivery/xezq/M4fVfG8aDFj67km55bx0zq4T6GD2pDey0FLirE8fLWj9wr8SB/tmpezereivw.mp4",
    "https://replicate.delivery/xezq/MuxZ4yqm7tq2ABGw3vs7e6X1VSeEdJT0lYQulXEOPIJL8KvUA/tmp1a2yky2b.mp4",
    "https://replicate.delivery/xezq/u2VHNaWXL8qfAC5ANwuUdkWclIBsFhJeYr4WrMSgH6ON8KvUA/tmp1c8kyysf.mp4",
    "https://replicate.delivery/xezq/YgKzGEIF6p7XLpByetWdHZQJdUprUno4ROynKa82g01GeKvUA/tmp249oz0zf.mp4",
    "https://replicate.delivery/xezq/954121H6vIL0IRQZmmJxd33N2MbZKGyxGhThqzduFp8fdlXKA/tmpik4cfby9.mp4",
    "https://replicate.delivery/xezq/DDbNKKfvGxXIJaXzh9D3xn6AfI7jXhhfeD8lfbXtn6TSgX5lC/tmp89gg0y0z.mp4",
    "https://replicate.delivery/xezq/vfc3emkNwzibJkUTZW9BXrgWeeKxZKN0vilyqCxsp6hqwr8SB/tmpw0sxesia.mp4",
    "https://replicate.delivery/xezq/7HWe4rEa4HyCIahqXA6RTP4DTAOuQBqBrMh9PYxmwp6f7KvUA/tmpzjw8g5y1.mp4"
  ],
  "background_audio": "https://apiboxfiles.erweima.ai/ODE3MjVlOTctNTk4Yi00NTFlLTllYzYtMzkxNjkzNzQ5N2Rl.mp3",
  "narration": "https://drive.google.com/uc?id=1r80RudLk3qTafXBD2epEkXkTdAaxahlE&export=download",
  "max_duration": 600
}

# Send the POST request
print("Sending request to merge videos and audio...")
start_time = time.time()

try:
    response = requests.post(url, json=data)
    
    # Check if the request was successful
    if response.status_code == 200:
        result = response.json()
        print(f"Success! Processing completed in {time.time() - start_time:.2f} seconds")
        print(f"Output file: {result['output_file']}")
        print(f"Message: {result['message']}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"An error occurred: {str(e)}")
