import argparse
from app.api.schemas import VMCreateRequest, VMActionRequest
from app.services.vm_manager import create_vm, start_vm, stop_vm, delete_vm


def main():
    parser = argparse.ArgumentParser("kvm-mgr-cli")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--image", required=True)
    p_create.add_argument("--cpu", type=int, default=1)
    p_create.add_argument("--memory", type=int, default=512)
    p_create.add_argument("--disk", type=int, default=10)

    p_start = sub.add_parser("start")
    p_start.add_argument("--name", required=True)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--name", required=True)

    p_delete = sub.add_parser("delete")
    p_delete.add_argument("--name", required=True)

    args = parser.parse_args()

    if args.cmd == "create":
        req = VMCreateRequest(
            name=args.name,
            image=args.image,
            cpu=args.cpu,
            memory_mb=args.memory,
            disk_gb=args.disk,
        )
        print(create_vm(req))
    elif args.cmd == "start":
        req = VMActionRequest(name=args.name)
        start_vm(req)
        print("started")
    elif args.cmd == "stop":
        req = VMActionRequest(name=args.name)
        stop_vm(req)
        print("stopped")
    elif args.cmd == "delete":
        req = VMActionRequest(name=args.name)
        delete_vm(req)
        print("deleted")


if __name__ == "__main__":
    main()
