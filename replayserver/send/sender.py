import asyncio
from asyncio.locks import Event
from contextlib import contextmanager

from replayserver.send.stream import DelayedReplayStream
from replayserver.errors import CannotAcceptConnectionError, \
    MalformedDataError


class Sender:
    def __init__(self, delayed_stream):
        self._stream = delayed_stream
        self._conn_count = 0
        self._ended = Event()
        self._closed = False
        self._stream_end_check = asyncio.ensure_future(
            self._stream.wait_for_ended())
        self._stream_end_check.add_done_callback(
            lambda f: None if f.cancelled() else self._check_ended())

    @classmethod
    def build(cls, stream):
        delayed_stream = DelayedReplayStream.build(stream)
        return cls(delayed_stream)

    def accepts_connections(self):
        return not self._stream.ended() and not self._closed

    @contextmanager
    def _connection_count(self, connection):
        self._conn_count += 1
        try:
            yield
        finally:
            self._conn_count -= 1
            self._check_ended()

    def _check_ended(self):
        if self._conn_count == 0 and self._stream.ended():
            self._stream_end_check.cancel()
            self._ended.set()

    async def handle_connection(self, connection):
        with self._connection_count(connection):
            if not self.accepts_connections():
                raise CannotAcceptConnectionError(
                    "Replay cannot be read from anymore")
            await self._write_header(connection)
            await self._write_replay(connection)

    async def _write_header(self, connection):
        header = await self._stream.wait_for_header()
        if header is None:
            raise MalformedDataError("Malformed replay header")
        await connection.write(header.data)

    async def _write_replay(self, connection):
        position = 0
        while not self._closed:
            data = await self._stream.wait_for_data(position)
            if not data:
                break
            position += len(data)
            await connection.write(data)

    def close(self):
        # This will prevent new connections and stop existing ones quickly.
        self._closed = True

    async def wait_for_ended(self):
        await self._ended.wait()
