---
skill_id: item_07_virtual_destructors
title: Declare destructors virtual in polymorphic base classes
source: Scott Meyers, Effective C++ (3rd ed.), Item 7
related: [cpp_core_guidelines_c35, item_05_compiler_generated_functions]
---

## Rule

If a class has at least one virtual function, it is meant to be used through
base-class pointers or references. Its destructor must then be either
**public and virtual** or **protected and non-virtual**.

## Why it matters

`delete` through a base-class pointer calls the destructor of the *static*
type. If that destructor isn't virtual, the behavior is undefined. In
practice only the base part is destroyed, so members and resources of the
derived class leak: file handles stay open, memory isn't freed, locks aren't
released.

## Example

```cpp
class Shape {
public:
    virtual double area() const = 0;   // polymorphic...
};                                      // ...but implicit destructor is not virtual

class Circle : public Shape { /* owns resources */ };

Shape* s = new Circle(1.0);
delete s;                               // undefined behavior: ~Circle() never runs
```

## Fix

```cpp
class Shape {
public:
    virtual ~Shape() = default;
    virtual double area() const = 0;
};
```

If objects must never be deleted through a base pointer (e.g. plugin or mixin
interfaces), make the destructor protected and non-virtual instead:

```cpp
class Plugin {
public:
    virtual void start() = 0;
protected:
    ~Plugin() = default;
};
```

## When not to apply

- Classes without virtual functions: a virtual destructor would add a vtable
  pointer to every object for no benefit (Item 7 also warns against this).
- Classes marked `final`: nothing can derive from them.
- Derived classes whose base already has a virtual destructor: their
  destructor is virtual automatically.

## Embedded note

A virtual destructor adds one vtable entry, not per-object cost beyond the
vtable pointer the class already has because of its other virtual
functions. There is no reason to skip it on microcontrollers.
