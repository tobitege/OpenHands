import argparse
import asyncio
import logging

from ohgradio.oh_interface import OHInterface
from openhands import __version__
from openhands.core.logger import openhands_logger as logger

cancel_event = asyncio.Event()
# logger.setLevel(logging.WARNING)
logger.setLevel(logging.DEBUG)


def get_parser() -> argparse.ArgumentParser:
    """Get the parser for the command line arguments."""
    parser = argparse.ArgumentParser(description='Run an agent with a specific task')

    # TODO: Add more arguments to e.g. override toml values, like --no-sandbox or --debug
    # Add the version argument
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=f'{__version__}',
        help='Show the version number and exit',
        default=None,
    )

    return parser


async def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.version:
        print(f'OpenHands version: {__version__}')
        return

    try:
        oh_interface = OHInterface()
        oh_interface.launch()
        while True:
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        logger.info('Received cancellation signal. Shutting down...')
    except KeyboardInterrupt:
        logger.info('Received keyboard interrupt. Shutting down...')
    finally:
        # Ensure all tasks are completed
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info('Shutdown complete.')


if __name__ == '__main__':
    asyncio.run(main())
