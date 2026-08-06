import http.server
import socketserver
import webbrowser
import os

PORT = 8080
DIRECTORY = os.path.join(os.path.dirname(__file__), "dashboard")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def start_dashboard():
    print("=" * 70)
    print(f"🚀 INICIANDO PAINEL WEB SAAS TRADEPILOT AI EM HTTP://LOCALHOST:{PORT}")
    print("=" * 70)
    
    webbrowser.open(f"http://localhost:{PORT}")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Painel encerrado pelo usuário.")

if __name__ == "__main__":
    start_dashboard()
