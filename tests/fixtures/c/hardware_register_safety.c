#define STATUS_READY   0x01u
#define STATUS_FAULT   0x02u
#define STATUS_TIMEOUT 0x04u
#define CONTROL_ENABLE 0x10u

typedef unsigned int uint32_t;

typedef struct {
    volatile uint32_t STATUS;
    volatile uint32_t CONTROL;
    volatile uint32_t ADC_VALUE;
} Peripheral;

extern int read_gpio_pin(int pin);

int hardware_register_safety(Peripheral *peripheral, int pin, int min_adc, int max_adc) {
    if (
        peripheral != 0 &&
        (peripheral->STATUS & STATUS_READY) &&
        !(peripheral->STATUS & STATUS_FAULT) &&
        !(peripheral->STATUS & STATUS_TIMEOUT) &&
        (peripheral->CONTROL & CONTROL_ENABLE) &&
        peripheral->ADC_VALUE >= min_adc &&
        peripheral->ADC_VALUE <= max_adc &&
        read_gpio_pin(pin)
    ) {
        return 1;
    }

    return 0;
}
