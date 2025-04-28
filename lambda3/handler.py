import logging
import random

def lambda_handler(event, context):

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()

    logger.log(logging.INFO, f"Event: {event}")
    logger.log(logging.INFO, f"Context: {context}")
    
    return {
        "oddNumbers": [1,3,5,7,9]
    }