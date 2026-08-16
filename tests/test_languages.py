"""Tests for Go / Java / C / C++ parsers (phase 04)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from hybrid_coco.config import get_index_path
from hybrid_coco.indexer import index_path
from hybrid_coco.parsers import detect_language, parse_file
from hybrid_coco.store import Store


def test_detect_language_new_extensions():
    assert detect_language("main.go") == "go"
    assert detect_language("App.java") == "java"
    assert detect_language("util.c") == "c"
    assert detect_language("util.h") == "c"
    assert detect_language("util.cpp") == "cpp"
    assert detect_language("util.hpp") == "cpp"
    assert detect_language("util.cc") == "cpp"
    assert detect_language("App.cs") == "csharp"


def test_go_parser_extracts_symbols():
    src = textwrap.dedent("""\
        package main
        import "fmt"
        // Login authenticates a user.
        func Login(user string) bool { return true }
        type User struct { Name string }
        func (u *User) Greet() string { return u.Name }
    """).encode()
    syms = parse_file(Path("main.go"), src)
    by_name = {s.name: s for s in syms}
    assert by_name["Login"].kind == "function"
    assert by_name["Login"].docstring and "authenticates" in by_name["Login"].docstring
    assert by_name["User"].kind == "class"
    assert by_name["Greet"].kind == "method"
    assert by_name["Greet"].parent_name == "User"
    assert any(s.kind == "import" for s in syms)


def test_java_parser_extracts_symbols():
    src = textwrap.dedent("""\
        package com.example;
        import java.util.List;
        /** Greeter greets people. */
        public class Greeter {
          /** Say hello. */
          public String greet(String name) { return name; }
        }
    """).encode()
    syms = parse_file(Path("Greeter.java"), src)
    by_name = {s.name: s for s in syms}
    assert by_name["Greeter"].kind == "class"
    assert by_name["Greeter"].docstring and "greets" in by_name["Greeter"].docstring
    assert by_name["greet"].kind == "method"
    assert by_name["greet"].parent_name == "Greeter"
    assert any(s.kind == "import" for s in syms)


def test_c_parser_extracts_symbols():
    src = textwrap.dedent("""\
        #include <stdio.h>
        /* add numbers */
        int add(int a, int b) { return a + b; }
        struct Point { int x; int y; };
    """).encode()
    syms = parse_file(Path("math.c"), src)
    by_name = {s.name: s for s in syms}
    assert by_name["add"].kind == "function"
    assert by_name["add"].docstring and "add numbers" in by_name["add"].docstring
    assert by_name["Point"].kind == "class"
    assert by_name["Point"].signature == "struct Point"
    assert any(s.kind == "import" for s in syms)


def test_cpp_parser_extracts_symbols():
    src = textwrap.dedent("""\
        #include <string>
        class Greeter {
        public:
          std::string greet(const std::string& name);
        };
        std::string Greeter::greet(const std::string& name) { return name; }
        int free_func(int x) { return x; }
    """).encode()
    syms = parse_file(Path("greeter.cpp"), src)
    methods = [s for s in syms if s.name == "greet"]
    assert methods
    assert all(s.kind == "method" for s in methods)
    assert all(s.parent_name == "Greeter" for s in methods)
    by_name = {s.name: s for s in syms}
    assert by_name["Greeter"].kind == "class"
    assert by_name["free_func"].kind == "function"


def test_csharp_parser_extracts_symbols():
    src = textwrap.dedent("""\
        using System;
        namespace Demo {
          /// <summary>Greeter greets people.</summary>
          public class Greeter {
            /// <summary>Say hello.</summary>
            public string Greet(string name) { return name; }
            public Greeter(int x) {}
          }
          public interface IService { void Run(); }
          public enum Status { Ok, Err }
          public struct Point { public int X; }
          public record Person(string Name);
        }
    """).encode()
    syms = parse_file(Path("Greeter.cs"), src)
    classes = {s.name: s for s in syms if s.kind == "class"}
    methods = [s for s in syms if s.kind == "method"]
    assert classes["Greeter"].docstring and "greets" in classes["Greeter"].docstring
    greet = next(s for s in methods if s.name == "Greet")
    assert greet.parent_name == "Greeter"
    assert greet.docstring and "hello" in greet.docstring
    assert classes["IService"].signature == "interface IService"
    assert classes["Status"].signature == "enum Status"
    assert classes["Point"].signature == "struct Point"
    assert classes["Person"].signature == "record Person"
    assert next(s for s in methods if s.name == "Run").parent_name == "IService"
    assert any(s.kind == "import" and "using System" in s.name for s in syms)
    ctors = [s for s in methods if s.name == "Greeter"]
    assert ctors
    assert ctors[0].parent_name == "Greeter"


def test_index_counts_new_languages(tmp_path: Path):
    (tmp_path / "main.go").write_text(
        'package main\nfunc Hello() {}\n', encoding="utf-8"
    )
    (tmp_path / "App.java").write_text(
        "public class App { public void run() {} }\n", encoding="utf-8"
    )
    (tmp_path / "util.c").write_text("int util(void) { return 1; }\n", encoding="utf-8")
    (tmp_path / "util.cpp").write_text("int cpp_util(int x) { return x; }\n", encoding="utf-8")
    (tmp_path / "App.cs").write_text(
        "public class AppCs { public void Run() {} }\n", encoding="utf-8"
    )

    result = index_path(tmp_path)
    assert result.indexed == 5
    assert result.errors == 0

    store = Store(get_index_path(tmp_path))
    try:
        langs = dict(store.languages())
        assert langs.get("go") == 1
        assert langs.get("java") == 1
        assert langs.get("c") == 1
        assert langs.get("cpp") == 1
        assert langs.get("csharp") == 1
        assert store.lookup_symbol("Hello")
        assert store.lookup_symbol("App")
        assert store.lookup_symbol("util")
        assert store.lookup_symbol("cpp_util")
        assert store.lookup_symbol("AppCs")
    finally:
        store.close()
