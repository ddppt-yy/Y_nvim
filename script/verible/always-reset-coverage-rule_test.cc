// Copyright 2017-2020 The Verible Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "verible/verilog/analysis/checkers/always-reset-coverage-rule.h"

#include <initializer_list>

#include "gtest/gtest.h"
#include "verible/common/analysis/linter-test-utils.h"
#include "verible/common/analysis/syntax-tree-linter-test-utils.h"
#include "verible/verilog/analysis/verilog-analyzer.h"
#include "verible/verilog/parser/verilog-token-enum.h"

namespace verilog {
namespace analysis {
namespace {

using verible::LintTestCase;
using verible::RunConfiguredLintTestCases;
using verible::RunLintTestCases;

TEST(AlwaysResetCoverageRule, BasicTests) {
  constexpr int kToken = TK_always;
  const std::initializer_list<LintTestCase> kTestCases = {
      // Empty module - no violations
      {""},
      {"module m;\nendmodule\n"},
      
      // Combinational always block - no violations
      {"module m;\nalways @* begin a = b; end\nendmodule"},
      
      // Sequential block without reset - no violations
      {"module m;\nalways @(posedge clk) begin a <= b; end\nendmodule"},
      
      // Sequential block with reset, all signals reset - no violations
      {"module m;\nalways @(posedge clk or posedge rst) begin\n"
       "  if (rst) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "  end\n"
       "end\nendmodule"},
      
      // Sequential block with reset, missing reset for signal
      {"module m;\n", {kToken, "always"}, " @(posedge clk or posedge rst) begin\n"
       "  if (rst) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "    c <= d;\n"
       "  end\n"
       "end\nendmodule"},
      
      // Multiple signals, some missing reset
      {"module m;\n", {kToken, "always"}, " @(posedge clk or posedge rst) begin\n"
       "  if (rst) begin\n"
       "    a <= 0;\n"
       "    b <= 0;\n"
       "  end else begin\n"
       "    a <= x;\n"
       "    b <= y;\n"
       "    c <= z;\n"
       "  end\n"
       "end\nendmodule"},
      
      // always_ff with reset, all signals reset - no violations
      {"module m;\nalways_ff @(posedge clk or posedge rst) begin\n"
       "  if (rst) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "  end\n"
       "end\nendmodule"},
      
      // always_ff with reset, missing reset
      {"module m;\n", {TK_always_ff, "always_ff"}, " @(posedge clk or posedge rst) begin\n"
       "  if (rst) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "    c <= d;\n"
       "  end\n"
       "end\nendmodule"},
      
      // Reset signal with different name (reset instead of rst)
      {"module m;\n", {kToken, "always"}, " @(posedge clk or posedge reset) begin\n"
       "  if (reset) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "    c <= d;\n"
       "  end\n"
       "end\nendmodule"},
      
      // Multiple always blocks
      {"module m;\n"
       "", {kToken, "always"}, " @(posedge clk or posedge rst) begin\n"
       "  if (rst) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "    c <= d;\n"
       "  end\n"
       "end\n"
       "always @(posedge clk) begin\n"
       "  e <= f;\n"
       "end\n"
       "endmodule"},
  };

  RunLintTestCases<VerilogAnalyzer, AlwaysResetCoverageRule>(kTestCases);
}

TEST(AlwaysResetCoverageRule, ConfiguredTests) {
  constexpr int kToken = TK_always;
  const std::initializer_list<LintTestCase> kTestCases = {
      // Custom reset keyword
      {"module m;\n", {kToken, "always"}, " @(posedge clk or posedge myreset) begin\n"
       "  if (myreset) begin\n"
       "    a <= 0;\n"
       "  end else begin\n"
       "    a <= b;\n"
       "    c <= d;\n"
       "  end\n"
       "end\nendmodule"},
  };

  RunConfiguredLintTestCases<VerilogAnalyzer, AlwaysResetCoverageRule>(
      kTestCases, "reset_keywords:myreset");
}

}  // namespace
}  // namespace analysis
}  // namespace verilog
