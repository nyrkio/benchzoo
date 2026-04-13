// Cypress configuration for the benchzoo sample benchmark.
//
// Cypress uses Mocha internally as its test runner, so mocha-junit-reporter
// plugs in naturally and emits standard JUnit XML. That XML is what the
// junit_cypress parser consumes. `toConsole: false` keeps Cypress's own
// spec runner output the only thing on stdout; the XML goes to
// ./output.xml next to this file.

const { defineConfig } = require('cypress');

module.exports = defineConfig({
  reporter: 'mocha-junit-reporter',
  reporterOptions: {
    mochaFile: 'output.xml',
    toConsole: false,
  },
  e2e: {
    // No baseUrl — the sample tests use `cy.visit('about:blank')` as a
    // trivial first step and do not exercise any real HTTP target.
    supportFile: false,
    video: false,
    screenshotOnRunFailure: false,
  },
});
