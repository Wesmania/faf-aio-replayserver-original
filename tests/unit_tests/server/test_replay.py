import pytest
import asynctest
import asyncio
from asynctest.helpers import exhaust_callbacks

from tests import timeout, fast_forward_time
from replayserver.server.replay import Replay
from replayserver.server.connection import ConnectionHeader
from replayserver.errors import MalformedDataError


@pytest.fixture
def mock_merger(locked_mock_coroutines):
    class M:
        canonical_stream = None

        async def handle_connection():
            pass

        def close():
            pass

        async def wait_for_ended():
            pass

    replay_end, ended_wait = locked_mock_coroutines()
    return asynctest.Mock(spec=M, _manual_end=replay_end,
                          wait_for_ended=ended_wait)


@pytest.fixture
def mock_sender(locked_mock_coroutines):
    class S:
        async def handle_connection():
            pass

        def close():
            pass

        async def wait_for_ended():
            pass

    replay_end, ended_wait = locked_mock_coroutines()
    return asynctest.Mock(spec=S, _manual_end=replay_end,
                          wait_for_ended=ended_wait)


@pytest.mark.asyncio
@fast_forward_time(1, 40)
@timeout(30)
async def test_replay_closes_after_timeout(
        event_loop, mock_merger, mock_sender, mock_bookkeeper):
    timeout = 15
    replay = Replay(mock_merger, mock_sender, mock_bookkeeper, timeout, 1)
    mock_merger.close.assert_not_called()
    mock_sender.close.assert_not_called()
    await asyncio.sleep(20)
    exhaust_callbacks(event_loop)
    mock_merger.close.assert_called()
    mock_sender.close.assert_called()

    mock_merger._manual_end.set()
    mock_sender._manual_end.set()
    await replay.wait_for_ended()


@pytest.mark.asyncio
@fast_forward_time(1, 40)
@timeout(30)
async def test_replay_close_cancels_timeout(
        event_loop, mock_merger, mock_sender, mock_bookkeeper):
    timeout = 15
    replay = Replay(mock_merger, mock_sender, mock_bookkeeper, timeout, 1)
    exhaust_callbacks(event_loop)
    replay.close()
    mock_merger.close.assert_called()
    mock_sender.close.assert_called()
    mock_merger.close.reset_mock()
    mock_sender.close.reset_mock()

    # Replay expects these to end after calling close
    mock_merger._manual_end.set()
    mock_sender._manual_end.set()

    await asyncio.sleep(20)
    exhaust_callbacks(event_loop)
    mock_merger.close.assert_not_called()
    mock_sender.close.assert_not_called()

    mock_merger._manual_end.set()
    mock_sender._manual_end.set()
    await replay.wait_for_ended()


@pytest.mark.asyncio
@fast_forward_time(1, 40)
@timeout(30)
async def test_replay_forwarding_connections(event_loop, mock_merger,
                                             mock_sender, mock_bookkeeper,
                                             mock_conn_plus_head):
    reader = mock_conn_plus_head(ConnectionHeader.Type.READER, 1)
    writer = mock_conn_plus_head(ConnectionHeader.Type.WRITER, 1)
    invalid = mock_conn_plus_head(17, 1)
    timeout = 15
    replay = Replay(mock_merger, mock_sender, mock_bookkeeper, timeout, 1)

    await replay.handle_connection(*reader)
    mock_merger.handle_connection.assert_not_awaited()
    mock_sender.handle_connection.assert_awaited_with(reader[1])
    mock_sender.handle_connection.reset_mock()

    await replay.handle_connection(*writer)
    mock_sender.handle_connection.assert_not_awaited()
    mock_merger.handle_connection.assert_awaited_with(writer[1])
    mock_merger.handle_connection.reset_mock()

    with pytest.raises(MalformedDataError):
        await replay.handle_connection(*invalid)
    mock_sender.handle_connection.assert_not_awaited()
    mock_merger.handle_connection.assert_not_awaited()

    mock_merger._manual_end.set()
    mock_sender._manual_end.set()
    await replay.wait_for_ended()


@pytest.mark.asyncio
@timeout(1)
async def test_replay_keeps_proper_event_order(
        event_loop, mock_merger, mock_sender, mock_bookkeeper):

    async def bookkeeper_check(*args, **kwargs):
        # Merging has to end before bookkeeping starts
        mock_merger.wait_for_ended.assert_awaited()
        # We shall not wait for stream sending to end before bookkeeping
        mock_sender.wait_for_ended.assert_not_awaited()
        return

    mock_bookkeeper.save_replay.side_effect = bookkeeper_check

    timeout = 0.1
    replay = Replay(mock_merger, mock_sender, mock_bookkeeper, timeout, 1)
    await exhaust_callbacks(event_loop)
    mock_merger._manual_end.set()
    await exhaust_callbacks(event_loop)
    mock_sender._manual_end.set()
    await replay.wait_for_ended()
