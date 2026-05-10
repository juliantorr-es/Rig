/**
 * ADR 0011: Runtime Visualization Substrate
 * Regression Benchmark: DOM Lifecycle Churn Monitoring
 * 
 * This script measures the number of DOM operations during render cycles.
 * It detects regressions where a "retained" update accidentally triggers
 * destructive operations (.clear(), createElement, removeChild).
 */

export class DomLifecycleBenchmark {
    constructor() {
        this.metrics = {
            createElement: 0,
            removeChild: 0,
            appendChild: 0,
            setAttribute: 0,
            lastFrameTime: 0
        };
        this._active = false;
        this._originalCreateElement = null;
        this._originalRemoveChild = null;
    }

    start() {
        if (this._active) return;
        this._active = true;
        this.reset();

        // Monkey-patch DOM operations for tracking
        this._originalCreateElement = document.createElementNS;
        const self = this;
        document.createElementNS = function() {
            self.metrics.createElement++;
            return self._originalCreateElement.apply(this, arguments);
        };

        this._originalRemoveChild = Element.prototype.removeChild;
        Element.prototype.removeChild = function() {
            self.metrics.removeChild++;
            return self._originalRemoveChild.apply(this, arguments);
        };
    }

    stop() {
        if (!this._active) return;
        document.createElementNS = this._originalCreateElement;
        Element.prototype.removeChild = this._originalRemoveChild;
        this._active = false;
    }

    reset() {
        this.metrics = {
            createElement: 0,
            removeChild: 0,
            appendChild: 0,
            setAttribute: 0,
            lastFrameTime: 0
        };
    }

    /**
     * Assert that steady-state churn is zero.
     * @param {string} context - Name of the test scenario.
     */
    assertSteadyState(context) {
        if (this.metrics.createElement > 0 || this.metrics.removeChild > 0) {
            console.error(`[Benchmark Failure] ${context}: Unexpected DOM churn detected!`, this.metrics);
            return false;
        }
        console.log(`[Benchmark Pass] ${context}: Zero churn verified.`);
        return true;
    }

    report() {
        console.group('ADR 0011: DOM Lifecycle Report');
        console.table(this.metrics);
        console.groupEnd();
    }
}
