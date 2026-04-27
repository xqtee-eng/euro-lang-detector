from src.config import APP_HOST, APP_PORT


def openapi_spec():
    base_url = f"http://{APP_HOST}:{APP_PORT}"
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "European Language Detector API",
            "version": "1.0.0",
            "description": "Hybrid language detection, word analysis, corpus management, and human-approved learning.",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/detect": {
                "post": {
                    "summary": "Detect the language of a text",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "text": {"type": "string"},
                                        "top_k": {"type": "integer", "default": 3},
                                    },
                                    "required": ["text"],
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Detection result"}},
                },
                "get": {
                    "summary": "Open detector web page",
                    "responses": {"200": {"description": "HTML"}},
                },
            },
            "/analyze": {
                "post": {
                    "summary": "Analyze every word in a text",
                    "responses": {"200": {"description": "Token-level analysis"}},
                }
            },
            "/corpus/files": {
                "get": {
                    "summary": "List reviewed corpus files",
                    "responses": {"200": {"description": "Corpus files"}},
                },
                "post": {
                    "summary": "Upload reviewed text for a language",
                    "responses": {"200": {"description": "Saved file"}},
                },
            },
            "/corpus/build": {
                "post": {
                    "summary": "Rebuild dataset/train/test from reviewed corpus files",
                    "responses": {"200": {"description": "Build stats"}},
                }
            },
            "/corpus/close-pack": {
                "post": {
                    "summary": "Apply curated close-language corpus sentences for bs/hr/sr and nb/nn",
                    "responses": {"200": {"description": "Applied pack"}},
                }
            },
            "/lexicon/items": {
                "get": {
                    "summary": "Search lexicon words",
                    "responses": {"200": {"description": "Words by language"}},
                },
                "post": {
                    "summary": "Add or import lexicon words",
                    "responses": {"200": {"description": "Saved words"}},
                },
                "delete": {
                    "summary": "Disable a lexicon word",
                    "responses": {"200": {"description": "Deleted word"}},
                },
            },
            "/names/items": {
                "get": {
                    "summary": "Search name hints",
                    "responses": {"200": {"description": "Name hints"}},
                },
                "post": {
                    "summary": "Add a name hint",
                    "responses": {"200": {"description": "Saved name"}},
                },
                "delete": {
                    "summary": "Disable a name hint",
                    "responses": {"200": {"description": "Deleted name"}},
                },
            },
            "/learn/items": {
                "get": {
                    "summary": "List active learning items",
                    "responses": {"200": {"description": "Learning queue"}},
                },
                "delete": {
                    "summary": "Clear active learning items",
                    "responses": {"200": {"description": "Clear result"}},
                },
            },
            "/runs.json": {
                "get": {
                    "summary": "List training runs",
                    "responses": {"200": {"description": "Training runs"}},
                }
            },
            "/safety.json": {
                "get": {
                    "summary": "Show learning safety policy",
                    "responses": {"200": {"description": "Safety policy"}},
                }
            },
        },
    }
