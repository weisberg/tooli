//! Procedural macros for the `tooli` crate.
//!
//! The only macro is `#[derive(TooliCli)]`, which generates a `tooli::Dispatch`
//! impl for a Clap subcommand enum. It removes the per-variant `match` arms and
//! the parallel "list of subcommand name strings" that every Tooli Rust CLI
//! would otherwise hand-maintain.

use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::quote;
use syn::{parse_macro_input, Data, DeriveInput, Fields, LitStr, Variant};

/// Derive a `tooli::Dispatch` impl for a Clap subcommand enum.
///
/// Each variant must be a single-tuple variant, e.g. `Find(FindArgs)`. The
/// inner type must implement `tooli::Command` and `schemars::JsonSchema`. The
/// CLI-facing name is the kebab-cased variant name (`FindFiles` → `find-files`)
/// unless overridden with `#[tooli(name = "...")]`.
#[proc_macro_derive(TooliCli, attributes(tooli))]
pub fn derive_tooli_cli(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    expand(input)
        .unwrap_or_else(syn::Error::into_compile_error)
        .into()
}

fn expand(input: DeriveInput) -> syn::Result<TokenStream2> {
    let enum_ident = input.ident;

    let Data::Enum(data) = input.data else {
        return Err(syn::Error::new_spanned(
            enum_ident,
            "TooliCli can only be derived on subcommand enums",
        ));
    };

    if data.variants.is_empty() {
        return Err(syn::Error::new_spanned(
            enum_ident,
            "TooliCli requires at least one subcommand variant",
        ));
    }

    let mut names = Vec::with_capacity(data.variants.len());
    let mut dispatch_arms = Vec::with_capacity(data.variants.len());
    let mut schema_arms = Vec::with_capacity(data.variants.len());
    let mut schemas = Vec::with_capacity(data.variants.len());

    for variant in &data.variants {
        let info = VariantInfo::from(variant)?;
        let variant_ident = &variant.ident;
        let inner_ty = info.inner_ty;
        let cli_name = info.cli_name;

        names.push(quote! { #cli_name });
        dispatch_arms.push(quote! {
            #enum_ident::#variant_ident(args) => app.run_command(#cli_name, args, options),
        });
        schema_arms.push(quote! {
            #cli_name => ::std::option::Option::Some(
                app.emit_command_schema::<#inner_ty>(#cli_name, mode)
            ),
        });
        schemas.push(quote! {
            ::tooli::command_schema::<#inner_ty>(#cli_name)
        });
    }

    Ok(quote! {
        impl ::tooli::Dispatch for #enum_ident {
            fn names() -> &'static [&'static str] {
                &[ #( #names ),* ]
            }

            fn dispatch(
                self,
                app: &::tooli::App,
                options: &::tooli::GlobalOptions,
            ) -> ::std::process::ExitCode {
                match self {
                    #( #dispatch_arms )*
                }
            }

            fn dispatch_schema(
                name: &str,
                app: &::tooli::App,
                mode: ::tooli::OutputMode,
            ) -> ::std::option::Option<::std::process::ExitCode> {
                match name {
                    #( #schema_arms )*
                    _ => ::std::option::Option::None,
                }
            }

            fn schemas() -> ::std::vec::Vec<::tooli::CommandSchema> {
                ::std::vec![ #( #schemas ),* ]
            }
        }
    })
}

struct VariantInfo<'a> {
    inner_ty: &'a syn::Type,
    cli_name: String,
}

impl<'a> VariantInfo<'a> {
    fn from(variant: &'a Variant) -> syn::Result<Self> {
        let Fields::Unnamed(fields) = &variant.fields else {
            return Err(syn::Error::new_spanned(
                variant,
                "TooliCli variants must be tuple-style: Variant(ArgsType)",
            ));
        };
        if fields.unnamed.len() != 1 {
            return Err(syn::Error::new_spanned(
                variant,
                "TooliCli variants must have exactly one field",
            ));
        }
        let inner_ty = &fields.unnamed[0].ty;
        let cli_name =
            override_name(variant)?.unwrap_or_else(|| to_kebab_case(&variant.ident.to_string()));
        Ok(Self { inner_ty, cli_name })
    }
}

fn override_name(variant: &Variant) -> syn::Result<Option<String>> {
    let mut found = None;
    for attr in &variant.attrs {
        if !attr.path().is_ident("tooli") {
            continue;
        }
        attr.parse_nested_meta(|meta| {
            if meta.path.is_ident("name") {
                let value: LitStr = meta.value()?.parse()?;
                found = Some(value.value());
                Ok(())
            } else {
                Err(meta.error("unsupported tooli attribute; only `name` is recognized"))
            }
        })?;
    }
    Ok(found)
}

fn to_kebab_case(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    for (i, ch) in input.chars().enumerate() {
        if ch.is_uppercase() {
            if i > 0 {
                out.push('-');
            }
            out.extend(ch.to_lowercase());
        } else {
            out.push(ch);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::to_kebab_case;

    #[test]
    fn kebab_case_handles_pascal_and_single_words() {
        assert_eq!(to_kebab_case("Find"), "find");
        assert_eq!(to_kebab_case("FindFiles"), "find-files");
        assert_eq!(to_kebab_case("HTTPGet"), "h-t-t-p-get");
        assert_eq!(to_kebab_case("read"), "read");
    }
}
