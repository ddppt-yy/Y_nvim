1. reset cover:

要关闭 always-reset-coverage 规则，可以使用 --rules 参数，在规则名前加 - 号：
--rules=-always-reset-coverage
例如：
verible-verilog-lint --rules=-always-reset-coverage your_file.sv
如果需要同时关闭多个规则，可以用逗号分隔：
--rules=-always-reset-coverage,-other-rule
也可以通过配置文件 .rules.verible_lint 来禁用规则，在文件中添加：
-always-reset-coverage


2. generate
--rules=+generate-label-prefix=prefix:A_





