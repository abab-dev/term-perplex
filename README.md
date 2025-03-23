# **Perplexity in Your Terminal 🚀**  

## We are using langroid for this
langroid is an amazing agents framwork with batteries included (and lots of starter examples)

## **Setup Instructions**  

### **1⃣ Create a `.env` File**  
Add your Gemini API key to a `.env` file in your project directory:  

```ini
GEMINI_API_KEY=your-gemini-api-key
```

---

### **2⃣ Install & Run ChromaDB with Docker**  
Ensure you have Docker installed on your system. Then, start ChromaDB by running:  

```sh
docker run -p 6333:6333 chromadb/chroma
```

---

### **3⃣ Set Up a Virtual Environment with `uv`**  
#### **Install `uv`**  
Follow the official installation guide: [uv Installation](https://docs.astral.sh/uv/getting-started/installation/)  

#### **Create and Activate a Virtual Environment**  
Run the following commands:  

```sh
uv venv --python=3.11
source .venv/bin/activate
```

#### **Install Dependencies**  
```sh
uv sync
```

---

### **4⃣ Run the Application**  
Finally, start the chat search script:  

```sh
python chat_search.py
```

Enjoy! 🎉🚀


