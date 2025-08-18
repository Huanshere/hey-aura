import requests
from ruamel.yaml import YAML
from pathlib import Path

yaml = YAML(typ='safe')
config_path = Path(__file__).resolve().parents[2] / "config.yaml"
with config_path.open("r", encoding="utf-8") as f:
    config = yaml.load(f) or {}

n8n_cfg = config.get("n8n", {})
username = n8n_cfg.get("username")
password = n8n_cfg.get("password")
get_emails_url = n8n_cfg.get("get_emails_url")
respond_to_email_url = n8n_cfg.get("respond_to_email_url")

def get_emails():
    if not username or not password or not get_emails_url:
        return print("invalid n8n settings")
    response = requests.post(get_emails_url, auth=(username, password))
    return response.text

def respond_to_email(message_id, text):
    if not username or not password or not respond_to_email_url:
        return print("invalid n8n settings")
    data = {"message_id": message_id, "text": text}
    response = requests.post(respond_to_email_url, data=data, auth=(username, password))
    return response.text

if __name__ == "__main__":
    get_emails()    