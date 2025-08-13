
# 🚧 Unstable Branch – `tsark_mcp` Setup & Usage

This branch is **unstable**.  
It’s where new features are added, tested, and occasionally break things.  
Expect bugs, experimental code, and rapid changes.  
If you want stability, use the `main` branch instead.  

---

## Launching `tsark_mcp`

This guide shows how to launch the `tsark_mcp` FastAPI server using exact terminal commands and sequence.

### Step 1: List project contents to confirm structure

```bash
ls
```

You should see:
```
mcp-agent  mcp-srv-tshark README.md
```
### Step 2: Access mcp-srv-tshark

```bash
cd mcp-srv
```

### Step 3: Create Python virtual environment


```bash
python -m venv env-mcp 
```
### Step 4: Activate the Python virtual environment
```bash
source venv-tshark-mcp/bin/activate
```
### Step 5 Install dependancies 
```bash
pip install -r requirements.txt
```

NB : make sure to add your own apikey to the fastagent.secrets.yaml file

### Step 6: Run the server
```bash
python server.py
```

If successful, you'll see output similar to:

```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5001 (Press CTRL+C to quit)
```

### Access the API

Open your browser and go to:

[http://localhost:5001/docs](http://localhost:5001/docs)

This opens the Swagger UI for interacting with the API.

## Launching `Fast-Agent`

This section explains how to launch the Fast-Agent and connect it to the `tsark_mcp` server.

### Step 1: Navigate to the Fast-Agent directory

```bash
cd mcp-agent
```
### Step 2: Create a virtual environment

```bash
python -m venv env-agent
```
### Step 3: Activate the virtual environment

```bash
source env-agent/bin/activate
```
### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Add your api key 

Create a new file for you api key : fastagent.secrets.yaml 

```
openai : 
  api_key: sk-.......

```

### Step 6: Check Fast-Agent setup (optional)

```bash
fast-agent check
```
### Step 7: Launch Fast-Agent

```bash
fast-agent go --model=openai --servers=tshark_mcp
```

That’s all you need to launch and operate both `tsark_mcp` and `Fast-Agent`.
