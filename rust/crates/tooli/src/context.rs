//! Runtime context passed to command implementations.

use crate::OutputMode;

/// Runtime context passed to command implementations.
///
/// Constructed by `App` from `GlobalOptions` and the per-invocation command
/// name; commands receive a clone. Use [`Context::builder`] when constructing
/// directly (tests, alternative runners).
#[derive(Debug, Clone)]
pub struct Context {
    pub app_name: String,
    pub command_name: String,
    pub output_mode: OutputMode,
    pub no_color: bool,
    pub quiet: bool,
    pub verbose: u8,
    pub dry_run: bool,
    pub yes: bool,
    pub caller_id: Option<String>,
}

impl Context {
    pub fn builder(app_name: impl Into<String>, command_name: impl Into<String>) -> ContextBuilder {
        ContextBuilder {
            app_name: app_name.into(),
            command_name: command_name.into(),
            output_mode: OutputMode::Auto,
            no_color: false,
            quiet: false,
            verbose: 0,
            dry_run: false,
            yes: false,
            caller_id: None,
        }
    }

    pub fn tool_id(&self) -> String {
        format!("{}.{}", self.app_name, self.command_name)
    }
}

/// Builder for [`Context`]. Replaces the previous 9-argument constructor.
#[derive(Debug, Clone)]
pub struct ContextBuilder {
    app_name: String,
    command_name: String,
    output_mode: OutputMode,
    no_color: bool,
    quiet: bool,
    verbose: u8,
    dry_run: bool,
    yes: bool,
    caller_id: Option<String>,
}

impl ContextBuilder {
    pub fn output_mode(mut self, mode: OutputMode) -> Self {
        self.output_mode = mode;
        self
    }

    pub fn no_color(mut self, value: bool) -> Self {
        self.no_color = value;
        self
    }

    pub fn quiet(mut self, value: bool) -> Self {
        self.quiet = value;
        self
    }

    pub fn verbose(mut self, value: u8) -> Self {
        self.verbose = value;
        self
    }

    pub fn dry_run(mut self, value: bool) -> Self {
        self.dry_run = value;
        self
    }

    pub fn yes(mut self, value: bool) -> Self {
        self.yes = value;
        self
    }

    pub fn caller_id(mut self, caller_id: Option<String>) -> Self {
        self.caller_id = caller_id;
        self
    }

    pub fn build(self) -> Context {
        Context {
            app_name: self.app_name,
            command_name: self.command_name,
            output_mode: self.output_mode,
            no_color: self.no_color,
            quiet: self.quiet,
            verbose: self.verbose,
            dry_run: self.dry_run,
            yes: self.yes,
            caller_id: self.caller_id,
        }
    }
}
