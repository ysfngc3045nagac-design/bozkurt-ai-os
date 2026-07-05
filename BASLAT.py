import os, subprocess, sys, time

os.system("pip install -q flask pyngrok numpy")

from pyngrok import ngrok

ngrok.kill()
ngrok.set_auth_token("3FGIBLlkzmJHbaMVwABf1izlbY3_5US9C7ibmm6HdQm4gm27u")

if not os.path.exists('/content/app2.py'):
    os.system("cp /content/drive/MyDrive/Bozkurtasena/app2.py /content/app2.py")

proc = subprocess.Popen([sys.executable, '/content/app2.py'])
time.sleep(4)

url = ngrok.connect(5001)
print(f"\n{'='*50}")
print(f"🐺 BOZKURT AI HAZIR!")
print(f"🌐 {url}")
print(f"{'='*50}")
