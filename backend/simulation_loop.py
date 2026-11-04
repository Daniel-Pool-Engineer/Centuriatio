import time
import threading
import concurrent.futures
from .simulation_state import WorldState
from .agent.agent import VillagerAgent


class BackendSimulation:
    def __init__(self, state: WorldState, llm_client):
        self.state = state
        self.llm_client = llm_client
        self.running = True
        self.pending_requests = {} 

        # isolated API calls to prevent cross-contamination. 
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers = 4)
        self.active_futures = {}

        self.last_flush_time = time.time()
        self.FLUSH_INTERVAL = 0.5

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def queue_agent(self, villager_id, agent, context):
        self.pending_requests[villager_id] = (villager_id, agent, context)

    def is_queued(self, villager_id):
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
            if self.pending_requests and len(self.active_futures) < 4:
                if current_time - self.last_flush_time >= self.FLUSH_INTERVAL:
                    #pop an agent from the queue
                    v_id = next(iter(self.pending_requests))
                    _, agent, ctx = self.pending_requests.pop(v_id)

                    print(f"[Backend] Dispatched isolated API call for {agent.name}")

                    #fire an isolated API call just for this one agent
                    future = self.executor.submit(agent.decide, ctx)
                    self.active_futures[v_id] = future
                    self.last_flush_time = current_time

            time.sleep(0.05)