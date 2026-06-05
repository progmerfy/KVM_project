import argparse
from app.api.schemas import VMCreateRequest, VMActionRequest, VMISORequest
from app.services.vm_manager import create_vm, start_vm, stop_vm, delete_vm, attach_iso, detach_iso


def main():
    parser = argparse.ArgumentParser("kvm-mgr-cli")
    parser.add_argument("--host-uri", default=None, help="libvirt host URI")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--image", required=True)
    p_create.add_argument("--iso", default=None, help="Path to OS installation ISO")
    p_create.add_argument("--cpu", type=int, default=1)
    p_create.add_argument("--memory", type=int, default=512)
    p_create.add_argument("--disk", type=int, default=10)
    p_create.add_argument("--network", default="default", help="libvirt network name")

    p_start = sub.add_parser("start")
    p_start.add_argument("--name", required=True)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--name", required=True)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--name", required=True)

    p_attach_iso = sub.add_parser("attach-iso")
    p_attach_iso.add_argument("--name", required=True)
    p_attach_iso.add_argument("--iso", required=True, help="Path to ISO image")

    p_detach_iso = sub.add_parser("detach-iso")
    p_detach_iso.add_argument("--name", required=True)

    args = parser.parse_args()
    host_uri = args.host_uri

    if args.cmd == "create":
        req = VMCreateRequest(
            name=args.name,
            image=args.image,
            iso_path=args.iso,
            cpu=args.cpu,
            memory_mb=args.memory,
            disk_gb=args.disk,
            network=args.network,
            host_uri=host_uri,
        )
        result = create_vm(req)
        print(f"VM created: {result.get('name')}")
        if result.get("ip_address"):
            print(f"IP address: {result['ip_address']}")
    elif args.cmd == "start":
        req = VMActionRequest(name=args.name, host_uri=host_uri)
        start_vm(req)
        print("started")
    elif args.cmd == "stop":
        req = VMActionRequest(name=args.name, host_uri=host_uri)
        stop_vm(req)
        print("stopped")
    elif args.cmd == "delete":
        req = VMActionRequest(name=args.name, host_uri=host_uri)
        delete_vm(req)
        print("deleted")
    elif args.cmd == "attach-iso":
        req = VMISORequest(name=args.name, iso_path=args.iso, host_uri=host_uri)
        attach_iso(req)
        print(f"ISO {args.iso} attached to {args.name}")
    elif args.cmd == "detach-iso":
        detach_iso(args.name, host_uri)
        print(f"CDROM detached from {args.name}")


if __name__ == "__main__":
    main()
