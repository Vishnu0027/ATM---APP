import uvicorn
import os
import sys

if __name__ == "__main__":
    # Ensure current directory is in sys.path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    print("=" * 60)
    print("Starting Multi-Bank Cardless ATM Application")
    print("=" * 60)
    print("User Web App : http://127.0.0.1:8000")
    print("ATM Machine  : http://127.0.0.1:8000/atm")
    print("API Docs     : http://127.0.0.1:8000/docs")
    print("Demo User    : arun@example.com / Password@123 (or mobile: 9876543210)")
    print("             : vishnu@gmail.com / 2006 (or mobile: 987654321)")
    print("=" * 60)

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
