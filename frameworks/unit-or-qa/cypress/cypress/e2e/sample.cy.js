// Canonical sample benchmark expressed as four Cypress end-to-end tests.
//
// Cypress itself is a browser-driving test runner, not a benchmark
// framework. We use it here as a "unit test runner as timing source"
// per docs/parser-targets.md section 6: mocha-junit-reporter records
// per-testcase wall time in the JUnit XML's `time` attribute, and when
// test names are stable that is a perfectly usable performance time
// series.
//
// Notes on Cypress idiom:
//   - Cypress commands (cy.*) are chainable and asynchronous; returning
//     a chain from the test body is how the runner knows when it's done.
//     We use `cy.wait(ms)` for sleeps (not `setTimeout` — that would
//     race with the Cypress command queue).
//   - Every test starts with `cy.visit('about:blank')` as a trivial
//     first step so Cypress has a page to attach to. The tests do not
//     exercise any real site.
//   - Tight CPU work (test 2, test 3) is plain synchronous JavaScript,
//     run inside a `.then()` so it sits inside the Cypress command
//     queue and its wall time is attributed to the test.

describe('benchzoo sample benchmark', () => {
  it('benchmark1', () => {
    // Sleep-dominated: ~2.15 s wall time.
    cy.visit('about:blank');
    cy.wait(2150);
  });

  it('benchmark2', () => {
    // Tight CPU loop, sub-millisecond. Touching `sink` keeps the body
    // observable so a sufficiently clever JS engine cannot elide it.
    cy.visit('about:blank');
    cy.then(() => {
      let sink = 0;
      for (let i = 0; i < 1000; i++) {
        sink += i;
      }
      expect(sink).to.equal(499500);
    });
  });

  it('benchmark3', () => {
    // Allocate and fill 1.4 MB. The browser (and Node-side Cypress
    // runner) has no direct /dev/null write API worth using here;
    // filling an ArrayBuffer is the closest in-process analogue and
    // exercises the same I/O-shaped timing bucket as the bash reference.
    cy.visit('about:blank');
    cy.then(() => {
      const N = 1_400_000;
      const buf = new Uint8Array(N);
      for (let i = 0; i < N; i++) {
        buf[i] = i & 0xff;
      }
      expect(buf.length).to.equal(N);
    });
  });

  it('benchmark4', () => {
    // Monthly change-point showcase. sleep_s = 2.15 + ((m mod 3) - 1),
    // with m the current UTC month (1..12). See
    // docs/sample-benchmark.md test 4.
    cy.visit('about:blank');
    const m = new Date().getUTCMonth() + 1; // getUTCMonth is 0-based
    const sleepMs = Math.round((2.15 + ((m % 3) - 1)) * 1000);
    cy.wait(sleepMs);
  });
});
