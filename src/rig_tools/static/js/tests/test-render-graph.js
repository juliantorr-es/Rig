/**
 * ADR 0011: Runtime Visualization Substrate
 * Unit Tests: Render Graph Determinism & Patching
 */

import { SceneGraphManager, RenderNode } from '../core/render-graph.js';

export class RenderGraphTestRunner {
    constructor() {
        this.container = document.createElement('div');
        this.manager = new SceneGraphManager(this.container);
    }

    async runAll() {
        console.group('ADR 0011: Render Graph Tests');
        try {
            await this.testRetentionIdentity();
            await this.testPatchingEfficiency();
            await this.testGarbageCollection();
            console.log('✅ All Render Graph tests passed.');
        } catch (err) {
            console.error('❌ Render Graph test failure:', err);
        }
        console.groupEnd();
    }

    /**
     * Test that node identity is preserved across render passes.
     */
    async testRetentionIdentity() {
        class MockNode extends RenderNode {
            render(parent) {
                const el = document.createElement('div');
                el.id = this.id;
                parent.appendChild(el);
                return el;
            }
            patch(el) {}
        }

        const node = new MockNode('test-node');
        
        // Pass 1: Render
        this.manager.patchPrimitive(node);
        const el1 = this.container.querySelector('#test-node');
        if (!el1) throw new Error('Node not rendered');

        // Pass 2: Patch
        this.manager.patchPrimitive(node);
        const el2 = this.container.querySelector('#test-node');
        
        if (el1 !== el2) {
            throw new Error('Identity lost: DOM element replaced instead of patched');
        }
    }

    /**
     * Test that patching avoids unnecessary render calls.
     */
    async testPatchingEfficiency() {
        let patchCount = 0;
        class PatchableNode extends RenderNode {
            patch(el) { patchCount++; }
            render(parent) { 
                const el = document.createElement('div');
                el.id = this.id;
                parent.appendChild(el);
                return el;
            }
        }

        const node = new PatchableNode('efficient-node');
        this.manager.patchPrimitive(node);
        this.manager.patchPrimitive(node);
        
        if (patchCount !== 1) {
            throw new Error(`Efficiency failure: expected 1 patch, got ${patchCount}`);
        }
    }

    /**
     * Test that unused nodes are pruned.
     */
    async testGarbageCollection() {
        const node1 = { id: 'node1', render: (p) => { 
            const el = document.createElement('div'); el.id = 'node1'; p.appendChild(el); return el;
        }, patch: () => {} };
        
        this.manager.patchPrimitive(node1);
        if (!this.container.querySelector('#node1')) throw new Error('Node 1 not found');

        // GC pass without node 1
        this.manager.garbageCollect(new Set(['something-else']));
        
        if (this.container.querySelector('#node1')) {
            throw new Error('Garbage collection failed: node 1 still in DOM');
        }
    }
}
