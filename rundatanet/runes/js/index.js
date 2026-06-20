// src/index.js
import * as module1 from './index_scripts.js';
import * as module2 from './index_multiselect.js';
import * as map_module from './index_map.js';
import * as query_builder_module from './index_query_builder.js';
import * as search_module from './index_search.js';
import * as view_model_module from './index_view_model.js';
import * as import_utils_module from './index_import_utils.js';
import * as layout_module from './index_layout.js';

Object.assign(window, module1, module2, map_module, query_builder_module, search_module, view_model_module, import_utils_module, layout_module);
layout_module.initCompactDbLayout();
