---
skill_id: item_13_use_objects_to_manage_resources
title: Use objects to manage resources (RAII)
source: Scott Meyers, Effective C++ (3rd ed.), Item 13
related: [item_14_copying_in_resource_managing_classes, item_16_matching_new_delete_forms, cpp_core_guidelines_r11]
---

## Rule

Acquire a resource and hand it to an owning object in the same expression.
The object's destructor releases the resource, so it is released on every
path out of the scope: normal flow, early `return`, `break`, or exception.
For heap memory the owning objects are `std::unique_ptr`, `std::shared_ptr`
and containers such as `std::vector`.

## Why it matters

A raw `new` paired with a manual `delete` depends on control flow reaching
the `delete` exactly once. Any early return or exception in between leaks
the memory; a second path that also deletes it is a double free. These bugs
appear long after the code was written, when someone adds a `return` or a
called function starts throwing.

## Example

```cpp
void process(const Config& cfg) {
    Parser* parser = new Parser(cfg);
    if (!parser->valid()) {
        return;                  // leak: delete is never reached
    }
    parser->run();               // leak if run() throws
    delete parser;
}
```

## Fix

```cpp
void process(const Config& cfg) {
    auto parser = std::make_unique<Parser>(cfg);
    if (!parser->valid()) {
        return;                  // released automatically
    }
    parser->run();               // released even if run() throws
}
```

For arrays use `std::vector<T>` (or `std::make_unique<T[]>(n)` when the
size is fixed after creation).

## When not to apply

- Placement new (`new (buffer) T`) constructs into memory owned elsewhere.
- A `delete` inside the destructor of a class that owns the pointer is a
  hand-written RAII class (Item 14 covers getting its copying right).
  Prefer a `std::unique_ptr` member anyway; then no destructor is needed.
- `std::unique_ptr<T>(new T)` and `p.reset(new T)` are safe, though
  `std::make_unique` is shorter and avoids naming the type twice.

## Embedded note

On microcontrollers, heap allocation itself is often restricted after
startup. RAII still applies: owning objects work just as well for static
pools, DMA buffers or peripheral handles, released in their destructor.
