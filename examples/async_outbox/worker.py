
import sqlite3
import time
import os

DB_PATH = "demo.db"

def worker_loop():
    print("[Worker] Started. Polling for events...")
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Fetch Pending
            c.execute("SELECT id, event_type, payload FROM outbox_events WHERE status='PENDING' LIMIT 1")
            row = c.fetchone()
            
            if row:
                eid, etype, payload = row
                print(f"[Worker] Processing Event {eid}: {etype} | Payload: {payload}")
                
                # Simulate Relay Logic
                time.sleep(1.0) 
                
                # Mark Complete
                c.execute("UPDATE outbox_events SET status='COMPLETED' WHERE id=?", (eid,))
                conn.commit()
                print(f"[Worker] Event {eid} COMPLETED.")
            else:
                # print(".", end="", flush=True)
                pass
            
            conn.close()
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Worker] Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("Waiting for DB...")
        time.sleep(2)
        
    worker_loop()
