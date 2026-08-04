import time


def response_timer(start_time):

    end_time = time.time()

    print(f"Response Time: {end_time - start_time:.2f} seconds")