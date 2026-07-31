//! Loads the sibling `routing-tables.json` at compile time.
//!
//! The JSON is the single source of truth for VSON-P -> Turtle role routing.
//! It lives inside the crate (`cli/src/penman/`) rather than next to the Python
//! reference so that `include_str!` never reaches outside the crate root — a
//! path outside it packages fine but fails the `cargo package` verify build,
//! which would make the crate unpublishable. The Python reference at
//! `tools/penman/vson_penman.py` reads this same file out of the checkout at
//! import time, so the two implementations still cannot drift — `make
//! cli-check` proves it by graph isomorphism over the gallery.

use once_cell::sync::Lazy;
use serde::Deserialize;
use std::collections::{HashMap, HashSet};

const ROUTING_JSON: &str = include_str!("routing-tables.json");

#[derive(Deserialize)]
struct Raw {
    namespaces: HashMap<String, String>,
    role_namespace_overrides: HashMap<String, String>,
    container_roles: Vec<String>,
    rcc_values: Vec<String>,
    role_value_to_vso: Vec<String>,
    role_value_to_rcc: Vec<String>,
    role_value_as_string: Vec<String>,
}

pub struct Routing {
    pub vso: String,
    pub allen: String,
    pub rcc: String,
    pub default: String,
    pub role_namespace_overrides: HashMap<String, String>,
    pub container_roles: HashSet<String>,
    pub rcc_values: HashSet<String>,
    pub role_value_to_vso: HashSet<String>,
    pub role_value_to_rcc: HashSet<String>,
    pub role_value_as_string: HashSet<String>,
}

pub static ROUTING: Lazy<Routing> = Lazy::new(|| {
    let raw: Raw = serde_json::from_str(ROUTING_JSON).expect("routing-tables.json malformed");
    // Strict resolution, mirroring the Python reference's KeyError: a missing
    // namespace must fail loudly, not silently emit IRIs in an empty namespace.
    let resolve = |key: &str| {
        raw.namespaces
            .get(key)
            .cloned()
            .unwrap_or_else(|| panic!("routing-tables.json: missing namespace {key:?}"))
    };
    let role_namespace_overrides = raw
        .role_namespace_overrides
        .iter()
        .map(|(role, ns_key)| (role.clone(), resolve(ns_key)))
        .collect();
    Routing {
        vso: resolve("vso"),
        allen: resolve("allen"),
        rcc: resolve("rcc"),
        default: resolve("default"),
        role_namespace_overrides,
        container_roles: raw.container_roles.into_iter().collect(),
        rcc_values: raw.rcc_values.into_iter().collect(),
        role_value_to_vso: raw.role_value_to_vso.into_iter().collect(),
        role_value_to_rcc: raw.role_value_to_rcc.into_iter().collect(),
        role_value_as_string: raw.role_value_as_string.into_iter().collect(),
    }
});
