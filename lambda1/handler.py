import logging
import random

def lambda_handler(event, context):

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger()

    logger.log(logging.INFO, f"Event: {event}")
    logger.log(logging.INFO, f"Context: {context}")
    
    return {
        "naturalNumbers": [1,2,3,4,5,6,7,8,9,10],
        "config": {
            "maxNumber": 10,
            "minNumber": 1
        }
    }