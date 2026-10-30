import { EventEmitter } from "node:events";

export type OrderStatus = "placed" | "packed" | "shipped" | "delivered" | "cancelled";

export interface StatusChanged {
  orderId: string;
  userId: string;
  from: OrderStatus;
  to: OrderStatus;
}

class OrderEvents extends EventEmitter {
  emitStatusChanged(e: StatusChanged): void {
    this.emit("statusChanged", e);
  }

  onStatusChanged(listener: (e: StatusChanged) => void | Promise<void>): void {
    this.on("statusChanged", listener);
  }
}

/** Process-wide order event bus. */
export const orderEvents = new OrderEvents();
