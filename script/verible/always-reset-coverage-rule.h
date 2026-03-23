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

#ifndef VERIBLE_VERILOG_ANALYSIS_CHECKERS_ALWAYS_RESET_COVERAGE_RULE_H_
#define VERIBLE_VERILOG_ANALYSIS_CHECKERS_ALWAYS_RESET_COVERAGE_RULE_H_

#include <cstddef>
#include <set>
#include <string>
#include <string_view>
#include <vector>

#include "absl/status/status.h"
#include "verible/common/analysis/lint-rule-status.h"
#include "verible/common/analysis/syntax-tree-lint-rule.h"
#include "verible/common/text/symbol.h"
#include "verible/common/text/syntax-tree-context.h"
#include "verible/verilog/analysis/descriptions.h"

namespace verilog {
namespace analysis {

// Checks that all signals assigned in sequential always blocks with reset
// are properly reset in the reset condition.
class AlwaysResetCoverageRule : public verible::SyntaxTreeLintRule {
 public:
  using rule_type = verible::SyntaxTreeLintRule;

  static const LintRuleDescriptor &GetDescriptor();

  absl::Status Configure(std::string_view configuration) final;
  void HandleSymbol(const verible::Symbol &symbol,
                    const verible::SyntaxTreeContext &context) final;

  verible::LintRuleStatus Report() const final;

 private:
  // Check if a signal name contains reset-related keywords
  bool IsResetSignal(std::string_view signal_name) const;

  // Extract signal name from an LValue node
  std::string ExtractSignalName(const verible::Symbol &lvalue) const;

  // Check if the always block is sequential (has posedge/negedge)
  bool IsSequentialBlock(const verible::Symbol &always_node) const;

  // Check if the always block has a reset signal in sensitivity list
  bool HasResetSignal(const verible::Symbol &always_node) const;

  // Get all signals assigned in the always block
  std::set<std::string> GetAllAssignedSignals(
      const verible::Symbol &always_node) const;

  // Get all signals reset in the reset condition
  std::set<std::string> GetResetSignals(
      const verible::Symbol &always_node) const;

  // Check if an if clause is checking for reset
  bool IsResetCondition(const verible::Symbol &if_clause) const;

 private:
  // Collected violations.
  std::set<verible::LintViolation> violations_;

  // Configuration: keywords to identify reset signals
  std::vector<std::string> reset_keywords_ = {"rst", "reset"};
};

}  // namespace analysis
}  // namespace verilog

#endif  // VERIBLE_VERILOG_ANALYSIS_CHECKERS_ALWAYS_RESET_COVERAGE_RULE_H_
