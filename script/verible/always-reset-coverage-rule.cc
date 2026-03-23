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

#include <algorithm>
#include <cctype>
#include <iterator>
#include <ostream>
#include <set>
#include <string_view>

#include "absl/status/status.h"
#include "absl/strings/str_join.h"
#include "verible/common/analysis/lint-rule-status.h"
#include "verible/common/analysis/matcher/bound-symbol-manager.h"
#include "verible/common/analysis/matcher/matcher.h"
#include "verible/common/analysis/syntax-tree-search.h"
#include "verible/common/text/concrete-syntax-leaf.h"
#include "verible/common/text/concrete-syntax-tree.h"
#include "verible/common/text/config-utils.h"
#include "verible/common/text/symbol.h"
#include "verible/common/text/syntax-tree-context.h"
#include "verible/common/text/tree-utils.h"
#include "verible/common/util/logging.h"
#include "verible/verilog/CST/verilog-matchers.h"
#include "verible/verilog/CST/verilog-nonterminals.h"
#include "verible/verilog/analysis/descriptions.h"
#include "verible/verilog/analysis/lint-rule-registry.h"

namespace verilog {
namespace analysis {

using verible::LintRuleStatus;
using verible::LintViolation;
using verible::SearchSyntaxTree;
using verible::SyntaxTreeContext;
using verible::matcher::Matcher;

//- Info --------------------------------------------------------------------
// Register AlwaysResetCoverageRule
VERILOG_REGISTER_LINT_RULE(AlwaysResetCoverageRule);

static constexpr std::string_view kMessage =
    "All signals assigned in sequential always blocks with reset "
    "should be reset in the reset condition.";

const LintRuleDescriptor &AlwaysResetCoverageRule::GetDescriptor() {
  static const LintRuleDescriptor d{
      .name = "always-reset-coverage",
      .topic = "sequential-logic",
      .desc =
          "Checks that all signals assigned in sequential always blocks "
          "with reset are properly reset in the reset condition.",
      .param = {{"reset_keywords", "rst,reset"}},
  };
  return d;
}

LintRuleStatus AlwaysResetCoverageRule::Report() const {
  return LintRuleStatus(violations_, GetDescriptor());
}

//- Configuration -----------------------------------------------------------
absl::Status AlwaysResetCoverageRule::Configure(
    const std::string_view configuration) {
  using verible::config::SetString;
  return verible::ParseNameValues(
      configuration, {{"reset_keywords",
                       [this](std::string_view value) {
                         reset_keywords_.clear();
                         std::string s(value);
                         size_t start = 0;
                         size_t end = s.find(',');
                         while (end != std::string::npos) {
                           reset_keywords_.push_back(s.substr(start, end - start));
                           start = end + 1;
                           end = s.find(',', start);
                         }
                         reset_keywords_.push_back(s.substr(start));
                         return absl::OkStatus();
                       }}});
}

//- Helper Functions --------------------------------------------------------
bool AlwaysResetCoverageRule::IsResetSignal(
    std::string_view signal_name) const {
  std::string lower_name(signal_name);
  std::transform(lower_name.begin(), lower_name.end(), lower_name.begin(),
                 [](unsigned char c) { return std::tolower(c); });
  
  for (const auto &keyword : reset_keywords_) {
    std::string lower_keyword(keyword);
    std::transform(lower_keyword.begin(), lower_keyword.end(),
                   lower_keyword.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    if (lower_name.find(lower_keyword) != std::string::npos) {
      return true;
    }
  }
  return false;
}

std::string AlwaysResetCoverageRule::ExtractSignalName(
    const verible::Symbol &lvalue) const {
  // Navigate through kLPValue -> kReference -> kLocalRoot -> kUnqualifiedId
  // -> SymbolIdentifier
  const verible::SyntaxTreeNode *node = verible::MaybeNode(&lvalue);
  if (!node) return "";
  
  // Check if this is kLPValue
  if (NodeEnum(node->Tag().tag) != NodeEnum::kLPValue) return "";
  
  if (node->empty()) return "";
  
  // Get kReference (first child)
  const verible::SyntaxTreeNode *ref_node =
      verible::MaybeNode(node->front().get());
  if (!ref_node || NodeEnum(ref_node->Tag().tag) != NodeEnum::kReference) {
    return "";
  }
  
  if (ref_node->empty()) return "";
  
  // Get kLocalRoot (first child of kReference)
  const verible::SyntaxTreeNode *local_root =
      verible::MaybeNode(ref_node->front().get());
  if (!local_root || NodeEnum(local_root->Tag().tag) != NodeEnum::kLocalRoot) {
    return "";
  }
  
  if (local_root->empty()) return "";
  
  // Get kUnqualifiedId (first child of kLocalRoot)
  const verible::SyntaxTreeNode *unqual_id =
      verible::MaybeNode(local_root->front().get());
  if (!unqual_id ||
      NodeEnum(unqual_id->Tag().tag) != NodeEnum::kUnqualifiedId) {
    return "";
  }
  
  if (unqual_id->empty()) return "";
  
  // Get SymbolIdentifier (first child of kUnqualifiedId)
  const verible::SyntaxTreeLeaf *ident_leaf =
      verible::MaybeLeaf(unqual_id->front().get());
  if (!ident_leaf) return "";
  
  return std::string(ident_leaf->get().text());
}

bool AlwaysResetCoverageRule::IsSequentialBlock(
    const verible::Symbol &always_node) const {
  // Find kEventControl nodes
  static const Matcher event_control_matcher{NodekEventControl()};
  std::vector<verible::TreeSearchMatch> event_controls =
      SearchSyntaxTree(always_node, event_control_matcher);
  
  for (const auto &ec_match : event_controls) {
    // Search for kEventExpression within kEventControl
    static const Matcher event_expr_matcher{NodekEventExpression()};
    std::vector<verible::TreeSearchMatch> event_exprs =
        SearchSyntaxTree(*ec_match.match, event_expr_matcher);
    
    for (const auto &expr_match : event_exprs) {
      const verible::SyntaxTreeNode *expr_node =
          verible::MaybeNode(expr_match.match);
      if (!expr_node || expr_node->empty()) continue;
      
      // Check first child for posedge or negedge
      const verible::SyntaxTreeLeaf *edge_leaf =
          verible::MaybeLeaf(expr_node->front().get());
      if (!edge_leaf) continue;
      
      std::string_view edge_text = edge_leaf->get().text();
      if (edge_text == "posedge" || edge_text == "negedge") {
        return true;
      }
    }
  }
  return false;
}

bool AlwaysResetCoverageRule::HasResetSignal(
    const verible::Symbol &always_node) const {
  // Find kEventControl nodes
  static const Matcher event_control_matcher{NodekEventControl()};
  std::vector<verible::TreeSearchMatch> event_controls =
      SearchSyntaxTree(always_node, event_control_matcher);
  
  for (const auto &ec_match : event_controls) {
    // Search for kEventExpression within kEventControl
    static const Matcher event_expr_matcher{NodekEventExpression()};
    std::vector<verible::TreeSearchMatch> event_exprs =
        SearchSyntaxTree(*ec_match.match, event_expr_matcher);
    
    for (const auto &expr_match : event_exprs) {
      const verible::SyntaxTreeNode *expr_node =
          verible::MaybeNode(expr_match.match);
      if (!expr_node || expr_node->size() < 2) continue;
      
      // Check first child for posedge or negedge
      const verible::SyntaxTreeLeaf *edge_leaf =
          verible::MaybeLeaf(expr_node->front().get());
      if (!edge_leaf) continue;
      
      std::string_view edge_text = edge_leaf->get().text();
      if (edge_text != "posedge" && edge_text != "negedge") continue;
      
      // Get the signal name (second child)
      auto children = expr_node->children();
      auto child_it = children.begin();
      if (child_it == children.end()) continue;
      ++child_it;  // Skip first child (edge type)
      if (child_it == children.end()) continue;
      const verible::Symbol *signal_symbol = child_it->get();
      if (!signal_symbol) continue;
      
      // Extract text from the signal
      const verible::SyntaxTreeLeaf *signal_leaf =
          verible::MaybeLeaf(signal_symbol);
      if (!signal_leaf) {
        // Try to find leaf in subtree
        signal_leaf = verible::GetLeftmostLeaf(*signal_symbol);
        if (!signal_leaf) {
          continue;
        }
      }
      
      if (IsResetSignal(signal_leaf->get().text())) {
        return true;
      }
    }
  }
  return false;
}

std::set<std::string> AlwaysResetCoverageRule::GetAllAssignedSignals(
    const verible::Symbol &always_node) const {
  std::set<std::string> signals;
  
  // Find all non-blocking assignments
  static const Matcher nonblocking_matcher{
      NodekNonblockingAssignmentStatement()};
  std::vector<verible::TreeSearchMatch> nonblocking_assigns =
      SearchSyntaxTree(always_node, nonblocking_matcher);
  
  // Find all blocking assignments
  static const Matcher blocking_matcher{NodekNetVariableAssignment()};
  std::vector<verible::TreeSearchMatch> blocking_assigns =
      SearchSyntaxTree(always_node, blocking_matcher);
  
  // Process all assignments
  for (const auto &assign_match : nonblocking_assigns) {
    const verible::SyntaxTreeNode *assign_node =
        verible::MaybeNode(assign_match.match);
    if (!assign_node || assign_node->empty()) continue;
    
    std::string signal_name = ExtractSignalName(*assign_node->front());
    if (!signal_name.empty()) {
      signals.insert(signal_name);
    }
  }
  
  for (const auto &assign_match : blocking_assigns) {
    const verible::SyntaxTreeNode *assign_node =
        verible::MaybeNode(assign_match.match);
    if (!assign_node || assign_node->empty()) continue;
    
    std::string signal_name = ExtractSignalName(*assign_node->front());
    if (!signal_name.empty()) {
      signals.insert(signal_name);
    }
  }
  
  return signals;
}

bool AlwaysResetCoverageRule::IsResetCondition(
    const verible::Symbol &if_clause) const {
  const verible::SyntaxTreeNode *if_node = verible::MaybeNode(&if_clause);
  if (!if_node || if_node->size() < 2) return false;
  
  // Get the if header (first child)
  auto children = if_node->children();
  auto child_it = children.begin();
  if (child_it == children.end()) return false;
  const verible::Symbol *if_header = child_it->get();
  if (!if_header) return false;
  
  // Get all text from the if header to check for reset signal
  std::string header_text = std::string(verible::StringSpanOfSymbol(*if_header));
  
  // Check if header contains reset keywords
  std::string lower_header(header_text);
  std::transform(lower_header.begin(), lower_header.end(), lower_header.begin(),
                 [](unsigned char c) { return std::tolower(c); });
  
  for (const auto &keyword : reset_keywords_) {
    std::string lower_keyword(keyword);
    std::transform(lower_keyword.begin(), lower_keyword.end(),
                   lower_keyword.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    if (lower_header.find(lower_keyword) != std::string::npos) {
      return true;
    }
  }
  
  return false;
}

std::set<std::string> AlwaysResetCoverageRule::GetResetSignals(
    const verible::Symbol &always_node) const {
  std::set<std::string> reset_signals;
  
  // Find all if clauses
  static const Matcher if_clause_matcher{NodekIfClause()};
  std::vector<verible::TreeSearchMatch> if_clauses =
      SearchSyntaxTree(always_node, if_clause_matcher);
  
  for (const auto &if_match : if_clauses) {
    if (!IsResetCondition(*if_match.match)) continue;
    
    const verible::SyntaxTreeNode *if_node =
        verible::MaybeNode(if_match.match);
    if (!if_node || if_node->size() < 2) continue;
    
    // Get the if body (second child)
    auto children = if_node->children();
    auto child_it = children.begin();
    if (child_it == children.end()) continue;
    ++child_it;  // Skip first child (if header)
    if (child_it == children.end()) continue;
    const verible::Symbol *if_body = child_it->get();
    if (!if_body) continue;
    
    // Find assignments in if body
    static const Matcher nonblocking_matcher{
        NodekNonblockingAssignmentStatement()};
    std::vector<verible::TreeSearchMatch> nonblocking_assigns =
        SearchSyntaxTree(*if_body, nonblocking_matcher);
    
    static const Matcher blocking_matcher{NodekNetVariableAssignment()};
    std::vector<verible::TreeSearchMatch> blocking_assigns =
        SearchSyntaxTree(*if_body, blocking_matcher);
    
    for (const auto &assign_match : nonblocking_assigns) {
      const verible::SyntaxTreeNode *assign_node =
          verible::MaybeNode(assign_match.match);
      if (!assign_node || assign_node->empty()) continue;
      
      std::string signal_name = ExtractSignalName(*assign_node->front());
      if (!signal_name.empty()) {
        reset_signals.insert(signal_name);
      }
    }
    
    for (const auto &assign_match : blocking_assigns) {
      const verible::SyntaxTreeNode *assign_node =
          verible::MaybeNode(assign_match.match);
      if (!assign_node || assign_node->empty()) continue;
      
      std::string signal_name = ExtractSignalName(*assign_node->front());
      if (!signal_name.empty()) {
        reset_signals.insert(signal_name);
      }
    }
  }
  
  return reset_signals;
}

//- Processing --------------------------------------------------------------
void AlwaysResetCoverageRule::HandleSymbol(const verible::Symbol &symbol,
                                           const SyntaxTreeContext &context) {
  // Only process kAlwaysStatement nodes
  if (NodeEnum(symbol.Tag().tag) != NodeEnum::kAlwaysStatement) return;
  
  // Check if this is a sequential block
  if (!IsSequentialBlock(symbol)) return;
  
  // Check is a sequential block, check if it has reset signal
  if (!HasResetSignal(symbol)) return;
  
  // Get all assigned signals
  std::set<std::string> all_signals = GetAllAssignedSignals(symbol);
  
  if (all_signals.empty()) return;
  
  // Get reset signals
  std::set<std::string> reset_signals = GetResetSignals(symbol);
  
  // Find missing reset signals
  std::set<std::string> missing_reset;
  std::set_difference(all_signals.begin(), all_signals.end(),
                      reset_signals.begin(), reset_signals.end(),
                      std::inserter(missing_reset, missing_reset.begin()));
  
  if (!missing_reset.empty()) {
    // Create violation message
    std::string message = "Sequential always block has reset but signals not reset: ";
    message += absl::StrJoin(missing_reset, ", ");
    
    // Find the location for the violation - report at the always block
    violations_.insert(LintViolation(symbol, message, context));
  }
}

}  // namespace analysis
}  // namespace verilog
