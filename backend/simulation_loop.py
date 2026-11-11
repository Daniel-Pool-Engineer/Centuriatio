import time
import threading
import concurrent.futures
from .simulation_state import WorldState

class BackendSimulation:
    """Handles background LLM API requests so the main game loop does not freeze."""

    def __init__(self, state: WorldState, llm_client):
        self.state = state
        self.llm_client = llm_client
        self.running = True

        # Waiting to be sent to the LLM.
        self.pending_requests = {} 

        # Isolated thread pool to run up to 10 API calls at the same time.
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = 10) # cap concurrent API calls

        # Currently being processed by the LLM.
        self.active_futures = {}

        self.last_flush_time = time.time()
        self.FLUSH_INTERVAL = 0.0


    def reset(self) -> None:
        # Clear previous runs.
        self.pending_requests.clear()
        self.active_futures.clear()

        # Safely clear the shared state using the lock
        with self.state.lock:
            self.state.new_actions.clear()
            self.state.is_data_ready = False
    
    def start(self):
        # Reference: https://www.geeksforgeeks.org/python/regular-threads-vs-daemon-threads-in-python/
        """ Single daemon thread that pumps the queue and gets results """
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()


    def shutdown(self) -> None:
        # Stop the loop and cancel any pending API calls immediately so the program can exit.
        self.running = False
        self.executor.shutdown(wait = False, cancel_futures = True)

    def queue_agent(self, villager_id, agent, context):
        """ Called from the main thread; the worker thread picks it up """
        self.pending_requests[villager_id] = (villager_id, agent, context)

    def is_queued(self, villager_id):
        """ True if the agent is waiting OR currently being processed """
        return villager_id in self.pending_requests or villager_id in self.active_futures

    def _run(self):
        while self.running:
            current_time = time.time()

            done_futures =[]

            # 1. Check if any isolated API calls have finished
            for v_id, future in self.active_futures.items():
                if future.done():
                    try:
                        action = future.result()
                        with self.state.lock:
                            self.state.new_actions[v_id] = action
                            self.state.is_data_ready = True
                    except Exception as e:
                        print(f"API Error for {v_id}:{e}")
                    done_futures.append(v_id)

            # remove finished tasks
            for v_id in done_futures:
                del self.active_futures[v_id]

            # 2. Dispatch new isolated calls
            if self.pending_requests and len(self.active_futures) < 10:
                if current_time - self.last_flush_time >=self.FLUSH_INTERVAL:

                    # pop the oldest agent from the queue
                    v_id = next(iter(self.pending_requests))
                    _, agent, ctx = self.pending_requests.pop(v_id)

                    print(f"[Backend] Dispatched isolated API call for {agent.name}")

                    # Submit the task to the thread pool. Each villager's decide() runs in parallel
                    future = self.executor.submit(agent.decide, ctx)
                    self.active_futures[v_id] = future
                    self.last_flush_time = current_time

            # Prevent CPU Burn
            time.sleep(0.05)