// Intentional Effective C++ violations for demos and manual testing.
// Run: python -m cli.main detect examples/sample_violations.cpp

// Item 7: polymorphic base class without a virtual destructor.
class Shape {
public:
    virtual double area() const = 0;
};

class Circle : public Shape {
public:
    explicit Circle(double r) : r_(r) {}
    double area() const override { return 3.14159 * r_ * r_; }

private:
    double r_;
};

// Correct: virtual destructor, nothing to report.
class Sensor {
public:
    virtual ~Sensor() = default;
    virtual float read() = 0;
};

// Correct: protected non-virtual destructor, can't be deleted through Plugin*.
class Plugin {
public:
    virtual void start() = 0;

protected:
    ~Plugin() = default;
};

void destroy(Shape* s) {
    delete s;  // undefined behavior if s points to a Circle
}
