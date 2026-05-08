/** Runtime Widget Registry
 *
 * PHASE 10: UI Convergence Pass
 * 
 * Central registry for all runtime instrumentation widgets.
 * Ensures consistent widget discovery, registration, and rendering.
 * 
 * Core doctrine:
 * - Projection-only rendering (never fetches data)
 * - No authority inference
 * - No timers as authority source
 * - Deterministic rendering
 * - Safe truncation
 * - textContent-only rendering
 * - Replay-safe rendering
 * - Advisory indicators
 * - Truthful animations derive from real backend/runtime state
 *
 * NO:
 * - fake thinking indicators
 * - meaningless shimmer
 * - arbitrary loading loops
 * - synthetic motion disconnected from runtime state
 * - decorative particle systems
 * - uncontrolled CSS chaos
 * - canvas-heavy visual effects
 * - hidden frontend state
 * - authority inference in UI
 * - direct backend mutation from widgets
 */

// Import all runtime widgets
// These are lazy-loaded to avoid circular dependencies
const widgetModules = {
    // PHASE 1-7: Instrumentation
    runtimeInstrumentation: () => import('./runtime-instrumentation.js'),
    
    // PHASE 3-4: Execution Panels
    runtimeExecutionPanel: () => import('./runtime-execution-panel.js'),
    
    // Existing widgets (to be normalized)
    runtimeConsoleCard: () => import('./runtime-console-card.js'),
    runtimeStatusCard: () => import('./runtime-status-card.js'),
    runtimeStreamCard: () => import('./runtime-stream-card.js'),
    runtimeProposalCard: () => import('./runtime-proposal-card.js'),
};

// =============================================================================
// Design System Constants
// =============================================================================

/** Runtime Widget Design System */
export const RuntimeWidgetDesign = {
    // Typography
    typo: {
        title: '16px',
        subtitle: '14px',
        body: '13px',
        small: '12px',
        tiny: '10px',
        mono: '12px',
        family: 'system-ui, -apple-system, sans-serif',
        monoFamily: 'monospace',
        weight: {
            normal: '400',
            bold: 'bold',
        },
    },
    
    // Spacing (multiples of 4px)
    spacing: {
        none: '0',
        xs: '4px',
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '24px',
        xxl: '32px',
    },
    
    // Colors
    colors: {
        primary: 'var(--text-primary, #e0e0e0)',
        secondary: 'var(--text-secondary, #888)',
        tertiary: 'var(--text-tertiary, #666)',
        
        bg: {
            primary: 'var(--bg-primary, #1a1a1a)',
            secondary: 'var(--bg-secondary, #1e1e1e)',
            tertiary: 'var(--bg-tertiary, #252526)',
        },
        
        border: 'var(--border, #404040)',
        borderActive: 'var(--border-active, #444)',
        
        severity: {
            debug: 'var(--color-debug, #888)',
            info: 'var(--color-info, #e0e0e0)',
            warning: 'var(--color-warning, #ffa500)',
            error: 'var(--color-error, #ff5555)',
            critical: 'var(--color-critical, #ff4444)',
            success: 'var(--color-success, #4CAF50)',
        },
    },
    
    // Border radius
    radius: {
        none: '0',
        sm: '2px',
        md: '4px',
        lg: '6px',
    },
    
    // Shadows
    shadows: {
        none: 'none',
        sm: '0 1px 2px rgba(0,0,0,0.3)',
        md: '0 2px 4px rgba(0,0,0,0.3)',
    },
    
    // Transitions (All tied to real state changes)
    transitions: {
        fast: '100ms ease-in-out',
        normal: '150ms ease-in-out',
        slow: '200ms ease-in-out',
        // State-specific durations
        streaming: '150ms',
        proposing: '250ms',
        validating: '300ms',
        replaying: '100ms',
        stalled: '0ms',
        completion: '500ms',
        failure: '200ms',
    },
    
    // Sizing
    sizes: {
        widget: {
            minWidth: '200px',
            maxWidth: '800px',
        },
        header: {
            height: '32px',
        },
    },
};

// =============================================================================
// Widget Metadata
// =============================================================================

/** Widget category types */
export const WidgetCategory = {
    INSTRUMENTATION: 'instrumentation',
    EXECUTION: 'execution',
    STREAM: 'stream',
    PROPOSAL: 'proposal',
    STATUS: 'status',
    CONSOLE: 'console',
};

/** Supported widget types */
export const WidgetType = {
    // PHASE 1-7: Instrumentation
    RUNTIME_INSTRUMENTATION: 'RuntimeInstrumentation',
    
    // PHASE 3-4: Execution Panels
    RUNTIME_EXECUTION_PANEL: 'RuntimeExecutionPanel',
    
    // Existing widgets
    RUNTIME_CONSOLE_CARD: 'RuntimeConsoleCard',
    RUNTIME_STATUS_CARD: 'RuntimeStatusCard',
    RUNTIME_STREAM_CARD: 'RuntimeStreamCard',
    RUNTIME_PROPOSAL_CARD: 'RuntimeProposalCard',
};

/** Widget metadata */
export const widgetMetadata = {
    [WidgetType.RUNTIME_INSTRUMENTATION]: {
        category: WidgetCategory.INSTRUMENTATION,
        title: 'Runtime Instrumentation',
        description: 'Core instrumentation state machine',
        src: './runtime-instrumentation.js',
        factory: 'RuntimeInstrumentation',
        isCore: true,
        requires: [],
    },
    
    [WidgetType.RUNTIME_EXECUTION_PANEL]: {
        category: WidgetCategory.EXECUTION,
        title: 'Runtime Execution Panel',
        description: 'Execution lane visualization and capability routing',
        src: './runtime-execution-panel.js',
        factory: 'renderRuntimeExecutionPanel',
        isCore: true,
        requires: ['RuntimeInstrumentation'],
    },
    
    [WidgetType.RUNTIME_CONSOLE_CARD]: {
        category: WidgetCategory.CONSOLE,
        title: 'Runtime Console',
        description: 'Console-style stream output',
        src: './runtime-console-card.js',
        factory: 'renderRuntimeConsoleCard',
        isCore: false,
        requires: [],
    },
    
    [WidgetType.RUNTIME_STATUS_CARD]: {
        category: WidgetCategory.STATUS,
        title: 'Runtime Status',
        description: 'Runtime status updates',
        src: './runtime-status-card.js',
        factory: 'renderRuntimeStatusCard',
        isCore: false,
        requires: [],
    },
    
    [WidgetType.RUNTIME_STREAM_CARD]: {
        category: WidgetCategory.STREAM,
        title: 'Runtime Stream',
        description: 'Live token/chunk rendering',
        src: './runtime-stream-card.js',
        factory: 'RuntimeStreamCard',
        isCore: false,
        requires: [],
    },
    
    [WidgetType.RUNTIME_PROPOSAL_CARD]: {
        category: WidgetCategory.PROPOSAL,
        title: 'Runtime Proposal',
        description: 'Proposal summaries from stream events',
        src: './runtime-proposal-card.js',
        factory: 'renderRuntimeProposalCard',
        isCore: false,
        requires: [],
    },
};

// =============================================================================
// Widget Registry
// =============================================================================

/** Central widget registry */
export class WidgetRegistry {
    constructor() {
        this._widgets = new Map();
        this._categories = new Map();
        this._initialized = false;
    }

    /** Initialize the registry (loads all widgets) */
    async initialize() {
        if (this._initialized) return this;
        
        for (const [name, loader] of Object.entries(widgetModules)) {
            try {
                const module = await loader();
                
                // Find the renderer function
                let renderer;
                if (module.default) {
                    renderer = module.default;
                } else {
                    // Look for renderXxx or Xxx function
                    const exportNames = Object.keys(module);
                    const renderName = exportNames.find(n => n.startsWith('render'));
                    if (renderName) {
                        renderer = module[renderName];
                    } else {
                        // Look for the widget class
                        const widgetName = name.replace(/([A-Z])/g, '_$1').toUpperCase();
                        renderer = module[widgetName] || exportNames.find(n => !n.startsWith('_'));
                    }
                }
                
                if (renderer) {
                    const widgetName = Object.keys(module).find(n => n === 'render' + name.replace(/^[a-z]/, c => c.toUpperCase())) || name;
                    this._widgets.set(widgetName, renderer);
                }
            } catch (error) {
                console.warn(`Failed to load widget module '${name}':`, error);
            }
        }
        
        // Organize by category
        for (const [name, meta] of Object.entries(widgetMetadata)) {
            if (!this._categories.has(meta.category)) {
                this._categories.set(meta.category, new Map());
            }
            this._categories.get(meta.category).set(name, meta);
        }
        
        this._initialized = true;
        return this;
    }

    /** Register a widget */
    register(name, renderer, metadata = {}) {
        if (this._widgets.has(name)) {
            console.warn(`Widget '${name}' already registered, overwriting`);
        }
        this._widgets.set(name, renderer);
        return this;
    }

    /** Unregister a widget */
    unregister(name) {
        this._widgets.delete(name);
        return this;
    }

    /** Get a widget renderer */
    get(name) {
        return this._widgets.get(name);
    }

    /** Check if widget exists */
    has(name) {
        return this._widgets.has(name);
    }

    /** Get all widgets */
    list() {
        return Array.from(this._widgets.entries());
    }

    /** Get widgets by category */
    listByCategory(category) {
        const widgets = [];
        const categoryWidgets = this._categories.get(category);
        if (categoryWidgets) {
            for (const [name] of categoryWidgets) {
                const renderer = this._widgets.get(name);
                if (renderer) {
                    widgets.push([name, renderer]);
                }
            }
        }
        return widgets;
    }

    /** Get widget metadata */
    getMetadata(name) {
        return widgetMetadata[name];
    }

    /** Get all categories */
    getCategories() {
        return Array.from(this._categories.keys());
    }

    /** Render a widget by type */
    render(type, id, data, context) {
        const renderer = this.get(type);
        if (!renderer) {
            console.warn(`No renderer found for widget type: ${type}`);
            return null;
        }
        
        try {
            // Inject instrumentation into context if not present
            if (!context.runtimeInstrumentation) {
                context = { ...context, runtimeInstrumentation: null };
            }
            
            return renderer(id, data, context);
        } catch (error) {
            console.error(`Error rendering widget '${type}':`, error);
            return this.renderErrorWidget(type, error, id, data, context);
        }
    }

    /** Render error fallback widget */
    renderErrorWidget(type, error, id, data, context) {
        const el = document.createElement('div');
        el.className = 'widget error-widget';
        el.id = id || `error-${type}`;
        el.style.padding = RuntimeWidgetDesign.spacing.md;
        el.style.backgroundColor = RuntimeWidgetDesign.colors.severity.error;
        el.style.color = RuntimeWidgetDesign.colors.bg.primary;
        el.style.borderRadius = RuntimeWidgetDesign.radius.md;
        el.style.fontFamily = RuntimeWidgetDesign.typo.family;
        el.style.fontSize = RuntimeWidgetDesign.typo.small;
        
        const title = document.createElement('h3');
        title.textContent = `Error: ${type}`;
        title.style.margin = '0';
        title.style.fontSize = RuntimeWidgetDesign.typo.body;
        title.style.fontWeight = RuntimeWidgetDesign.typo.weight.bold;
        el.appendChild(title);
        
        const message = document.createElement('p');
        message.textContent = error.message;
        message.style.margin = RuntimeWidgetDesign.spacing.sm + ' 0';
        el.appendChild(message);
        
        const code = document.createElement('code');
        code.textContent = error.stack || String(error);
        code.style.display = 'block';
        code.style.marginTop = RuntimeWidgetDesign.spacing.sm;
        code.style.fontFamily = RuntimeWidgetDesign.typo.monoFamily;
        code.style.fontSize = RuntimeWidgetDesign.typo.tiny;
        code.style.whiteSpace = 'pre-wrap';
        code.style.maxHeight = '100px';
        code.style.overflowY = 'auto';
        el.appendChild(code);
        
        // Advisory notice
        const advisory = document.createElement('p');
        advisory.textContent = 'Widget rendering is advisory only.';
        advisory.style.marginTop = RuntimeWidgetDesign.spacing.sm;
        advisory.style.fontSize = RuntimeWidgetDesign.typo.tiny;
        advisory.style.opacity = '0.7';
        advisory.style.fontStyle = 'italic';
        el.appendChild(advisory);
        
        return el;
    }

    /** Clear all widgets */
    clear() {
        this._widgets.clear();
        this._initialized = false;
        return this;
    }

    /** Get the current design system */
    getDesign() {
        return RuntimeWidgetDesign;
    }
}

// =============================================================================
// Global Registry Instance
// =============================================================================

// Singleton registry instance
const globalRegistry = new WidgetRegistry();

/** Get the global widget registry */
export function getRegistry() {
    return globalRegistry;
}

/** Initialize the global registry */
export async function initializeRegistry() {
    return await globalRegistry.initialize();
}

// =============================================================================
// Widget Rendering Utilities
// =============================================================================

/** Render a widget with advisory notice */
export function renderWithAdvisory(renderer, id, data, context, advisoryText = null) {
    const content = renderer(id, data, context);
    
    // Add advisory notice if not already present
    if (advisoryText && !content.querySelector('.advisory-notice')) {
        const advisoryEl = document.createElement('div');
        advisoryEl.className = 'advisory-notice';
        advisoryEl.style.marginTop = RuntimeWidgetDesign.spacing.sm;
        advisoryEl.style.fontSize = RuntimeWidgetDesign.typo.tiny;
        advisoryEl.style.color = RuntimeWidgetDesign.colors.secondary;
        advisoryEl.style.fontStyle = 'italic';
        advisoryEl.textContent = advisoryText;
        content.appendChild(advisoryEl);
    }
    
    return content;
}

/** Apply consistent styling to widget */
export function styleWidget(el, options = {}) {
    const design = RuntimeWidgetDesign;
    
    el.style.fontFamily = options.fontFamily || design.typo.family;
    el.style.fontSize = options.fontSize || design.typo.body;
    el.style.color = options.color || design.colors.primary;
    el.style.backgroundColor = options.background || design.colors.bg.secondary;
    el.style.borderRadius = options.radius || design.radius.md;
    el.style.padding = options.padding || design.spacing.md;
    
    if (options.border !== false) {
        el.style.border = `1px solid ${design.colors.border}`;
    }
    
    return el;
}

/** Create a consistent badge element */
export function createBadge(text, severity = 'info', options = {}) {
    const design = RuntimeWidgetDesign;
    
    const el = document.createElement('span');
    el.className = `badge severity-${severity}`;
    el.style.display = 'inline-flex';
    el.style.alignItems = 'center';
    el.style.fontSize = options.fontSize || design.typo.tiny;
    el.style.fontWeight = options.fontWeight || design.typo.weight.bold;
    el.style.padding = options.padding || `2px ${design.spacing.sm}`;
    el.style.borderRadius = options.radius || design.radius.sm;
    el.style.color = design.colors.severity[severity] || design.colors.primary;
    el.style.backgroundColor = options.background || 'rgba(128, 128, 128, 0.2)';
    el.style.textTransform = 'uppercase';
    el.textContent = text;
    
    return el;
}

/** Create a consistent stat item */
export function createStatItem(label, value, options = {}) {
    const design = RuntimeWidgetDesign;
    
    const el = document.createElement('span');
    el.className = 'stat-item';
    el.style.display = 'inline-flex';
    el.style.alignItems = 'center';
    el.style.gap = design.spacing.sm;
    
    const labelEl = document.createElement('span');
    labelEl.style.color = design.colors.secondary;
    labelEl.style.fontSize = design.typo.small;
    labelEl.textContent = label + ':';
    el.appendChild(labelEl);
    
    const valueEl = document.createElement('span');
    valueEl.style.color = design.colors.primary;
    valueEl.style.fontWeight = design.typo.weight.bold;
    valueEl.style.fontSize = design.typo.small;
    valueEl.textContent = value;
    el.appendChild(valueEl);
    
    return el;
}

// =============================================================================
// Normalization Utilities
// =============================================================================

/** Normalize common data fields */
export function normalizeData(data, defaults = {}) {
    return {
        id: data.id || defaults.id,
        title: data.title || defaults.title,
        stream_id: data.stream_id || data.streamId || defaults.stream_id,
        invocation_id: data.invocation_id || data.invocationId || defaults.invocation_id,
        provider_id: data.provider_id || data.providerId || defaults.provider_id,
        ...data,
    };
}

/** Format timestamp consistently */
export function formatTimestamp(ts) {
    if (!ts) return '';
    try {
        const date = new Date(ts);
        return date.toISOString().split('T')[1].split('.')[0];
    } catch {
        return String(ts).substring(0, 12);
    }
}

/** Truncate text consistently */
export function truncateText(text, maxLen = 40) {
    if (!text) return '';
    const str = String(text);
    if (str.length <= maxLen) return str;
    return str.substring(0, maxLen - 3) + '...';
}

/** Format number with commas */
export function formatNumber(num) {
    if (num === undefined || num === null) return '0';
    return Number(num).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}
