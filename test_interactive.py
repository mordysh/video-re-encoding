import pty
import os
import subprocess
import time
import select

def test_controls():
    master_fd, slave_fd = pty.openpty()
    
    # Run the script in the slave PTY
    p = subprocess.Popen(
        ["python3", "encode_h265.py"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True
    )
    
    os.close(slave_fd)
    
    output = b""
    
    print("Wait for encoding to start...")
    time.sleep(3)
    
    print("Testing P (Pause)...")
    os.write(master_fd, b"p")
    time.sleep(2)
    
    print("Testing R (Resume)...")
    os.write(master_fd, b"r")
    time.sleep(2)
    
    print("Testing Q (Quit)...")
    os.write(master_fd, b"q")
    
    # Wait for process to exit
    try:
        p.wait(timeout=5)
        print("Process exited successfully.")
    except subprocess.TimeoutExpired:
        print("Process failed to exit on Q, killing...")
        p.kill()
            
    # Read output
    while True:
        r, _, _ = select.select([master_fd], [], [], 0.5)
        if r:
            try:
                data = os.read(master_fd, 4096)
                if not data: break
                output += data
            except OSError:
                break
        else:
            break
            
    os.close(master_fd)
    
    decoded_output = output.decode('utf-8', errors='ignore')
    # print(decoded_output) # For debugging
    
    paused_confirmed = "[PAUSED]" in decoded_output
    quit_confirmed = "aborted by user" in decoded_output or "Encoding complete!" in decoded_output

    if paused_confirmed:
        print("✓ Pause confirmed.")
    else:
        print("✗ Pause NOT confirmed.")

    if quit_confirmed:
        print("✓ Quit confirmed.")
    else:
        print("✗ Quit NOT confirmed.")

    return paused_confirmed and quit_confirmed

if __name__ == "__main__":
    if test_controls():
        print("\nALL TESTS PASSED")
    else:
        print("\nTESTS FAILED")
