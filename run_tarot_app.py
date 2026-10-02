#!/usr/bin/env python3
import subprocess # this is what allows you to close the app/network port
import webbrowser # this is what allows you to open the app in a browser
import time
import sys
import os

def main():
    print("Starting Tarot Card Reader App...")
    print("Working directory:", os.getcwd()) # See if the directory is pointed to the right spot
    
    # Change to the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    try:
        # Start the app
        print("Launching Dash server...")
        print("App will be available at: http://127.0.0.1:8050")
        print("Use the 'Stop Server' button in the app OR press Ctrl+C to stop from terminal")
        print()
        
        # Open browser after a short delay to allow the elements to populate
        def open_browser():
            time.sleep(2)
            webbrowser.open("http://127.0.0.1:8050")
        
        import threading
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Run the app
        subprocess.run([sys.executable, "tarot_reader_app.py"])
        
    except KeyboardInterrupt:
        print("\n Stopping server")
    except Exception as e:
        print(f"Error starting app: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()