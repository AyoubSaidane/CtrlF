```bash
# create a venv and activate environment
python -m venv venv
source venv/bin/activate

# install requirements
pip install -r requirements.txt
```

# configure your .env file
create an OPENAI_API_KEY
create a Supabase account and configure the connection URL and API key

```bash
# parse documents
python3 rag/parser.py

# embed parsed documents
python3 rag/embeder.py

# start a local server
python3 rag/processor.py

# install react dependencies
npm install

# start your app
npm run dev
```