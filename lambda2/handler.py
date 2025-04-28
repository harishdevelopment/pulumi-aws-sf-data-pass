import logging
import random

def lambda_handler(event, context):

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()

    logger.log(logging.INFO, f"Event: {event}")
    logger.log(logging.INFO, f"Context: {context}")
    
    return {"evenNumbers": [2,4,6,8,10]}