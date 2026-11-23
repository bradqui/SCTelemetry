"""Runtime message classes for the game's telemetry service, from reflection or a protoset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import grpc
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.descriptor import MethodDescriptor, ServiceDescriptor

from .protoset import SERVICE_NAME


@dataclass
class TelemetrySchema:
    pool: descriptor_pool.DescriptorPool
    service: ServiceDescriptor
    file_set: descriptor_pb2.FileDescriptorSet
    source: str

    # -- construction

    @classmethod
    def from_file_set(
        cls, file_set: descriptor_pb2.FileDescriptorSet, source: str
    ) -> TelemetrySchema:
        pool = descriptor_pool.DescriptorPool()
        for fdp in file_set.file:
            pool.AddSerializedFile(fdp.SerializeToString())
        service = pool.FindServiceByName(SERVICE_NAME)
        return cls(pool=pool, service=service, file_set=file_set, source=source)

    @classmethod
    def from_protoset(cls, path: Path) -> TelemetrySchema:
        file_set = descriptor_pb2.FileDescriptorSet.FromString(path.read_bytes())
        return cls.from_file_set(file_set, f"protoset:{path}")

    @classmethod
    def from_reflection(cls, channel: grpc.Channel) -> TelemetrySchema:
        """Ask the game's server for its definitions. Raises grpc.RpcError if reflection is off."""
        from grpc_reflection.v1alpha.proto_reflection_descriptor_database import (
            ProtoReflectionDescriptorDatabase,
        )

        db = ProtoReflectionDescriptorDatabase(channel)
        root = db.FindFileContainingSymbol(SERVICE_NAME)
        ordered: list[descriptor_pb2.FileDescriptorProto] = []
        seen: set[str] = set()

        def visit(fdp: descriptor_pb2.FileDescriptorProto) -> None:
            if fdp.name in seen:
                return
            seen.add(fdp.name)
            for dep in fdp.dependency:
                visit(db.FindFileByName(dep))
            ordered.append(fdp)

        visit(root)
        return cls.from_file_set(descriptor_pb2.FileDescriptorSet(file=ordered), "reflection")

    # -- lookups

    def method(self, name: str) -> MethodDescriptor:
        return self.service.methods_by_name[name]

    def path(self, name: str) -> str:
        return f"/{self.service.full_name}/{name}"

    def request_class(self, method: str):
        return message_factory.GetMessageClass(self.method(method).input_type)

    def response_class(self, method: str):
        return message_factory.GetMessageClass(self.method(method).output_type)

    def describe(self) -> str:
        lines = [f"{self.service.full_name}  (from {self.source})"]
        for m in self.service.methods:
            kind = (
                ("stream " if m.client_streaming else "")
                + f"{m.input_type.full_name} -> "
                + ("stream " if m.server_streaming else "")
                + m.output_type.full_name
            )
            lines.append(f"  {m.name}: {kind}")
        return "\n".join(lines)
