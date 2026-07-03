from loguru import logger


def log_command_start(command_name: str, params: dict):
    """Helper function to log command start with parameters"""
    logger.info(f"=== Starting {command_name} command ===")
    logger.info("Command parameters:")
    for param, value in params.items():
        logger.info(f"  • {param}: {value}")


def log_command_summary(stats: dict):
    """Helper function to log command summary statistics"""
    logger.info("=== Command summary ===")
    for stat, value in stats.items():
        logger.info(f"  • {stat}: {value}")
