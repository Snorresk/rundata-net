=======================================
Publishing to Azure as an Azure Web App
=======================================

This page describes how to publish Rundata-net to Azure as a Linux
Azure Web App (App Service). It covers forking the repository on
GitHub, wiring up a GitHub Actions workflow for continuous
deployment, and configuring the environment variables expected by
the Django ``production`` settings.

.. contents::
   :local:
   :depth: 2

Prerequisites
=============

* An Azure subscription with permissions to create resource groups,
  App Service plans and Web Apps.
* A GitHub account that will host your fork of Rundata-net.
* A PostgreSQL database reachable from the Web App. In production
  Rundata-net runs against **Azure Database for PostgreSQL Flexible
  Server**, but any PostgreSQL instance accepted by
  ``dj-database-url`` works.
* Optionally, an Application Insights resource for monitoring.

1. Fork the repository on GitHub
================================

#. Open https://github.com/ and sign in.
#. Navigate to the upstream Rundata-net repository and click
   **Fork** to create a copy under your own account or organization.
#. Clone your fork locally if you want to make changes before the
   first deployment::

    $ git clone https://github.com/<your-account>/rundata-net.git
    $ cd rundata-net

All deployments to Azure will be triggered from pushes to this fork,
so make sure it is the repository you configure below.

2. Create the Azure Web App
===========================

Create a Linux App Service running Python 3.12. Reproduce the
following configuration through the Azure Portal, the Azure CLI, or
Infrastructure-as-Code of your choice:

* **Kind**: Linux Web App (``app,linux``).
* **Runtime stack**: ``PYTHON|3.12``.
* **App Service plan**: a Linux plan sized for your workload.
* **HTTPS Only**: enabled.
* **Minimum TLS version**: ``1.2``; disable FTP/FTPS.
* **VNet integration** *(optional)*: attach the Web App to a subnet
  if you need private connectivity to PostgreSQL or other backend
  resources.
* **Custom domains**: bind your apex domain and ``www`` subdomain
  (for example ``example.com`` and ``www.example.com``) with SNI
  SSL certificates.

Example using the Azure CLI::

    $ az group create --name <rg> --location <region>
    $ az appservice plan create \
        --name <plan-name> \
        --resource-group <rg> \
        --is-linux --sku B1
    $ az webapp create \
        --name <your-app-name> \
        --resource-group <rg> \
        --plan <plan-name> \
        --runtime "PYTHON:3.12"

3. Configure GitHub Actions for deployment
==========================================

The recommended deployment method is the built-in **Deployment
Center → GitHub Actions** integration of App Service:

#. In the Azure Portal, open your Web App.
#. Go to **Deployment Center**.
#. Choose **GitHub** as the source and authorize Azure to access
   your fork.
#. Select the organization, repository (your fork) and branch
   (typically ``main``).
#. For the build provider, choose **GitHub Actions** and pick the
   **Python 3.12** runtime stack.
#. Click **Save**.

Azure will:

* commit a workflow file under ``.github/workflows/`` in your fork
  that builds the project and deploys it with the
  ``azure/webapps-deploy`` action;
* add a publish profile (or a federated OIDC credential) as a
  GitHub Actions secret used by the workflow.

From that point on, every push to the configured branch triggers a
new build and deploy.

If you prefer to manage the workflow yourself, copy the generated
file into your fork and keep it under version control. A minimal
workflow installs Python 3.12, installs
``requirements/production.txt``, collects static files and deploys::

    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - run: pip install -r requirements/production.txt
    - run: python manage.py collectstatic --noinput
      env:
        DJANGO_SETTINGS_MODULE: config.settings.production
        DJANGO_SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
    - uses: azure/webapps-deploy@v3
      with:
        app-name: <your-app-name>
        publish-profile: ${{ secrets.AZUREAPPSERVICE_PUBLISHPROFILE }}

4. Configure environment variables on Azure
===========================================

Rundata-net uses ``django-environ`` to read configuration from the
process environment. On Azure, set these values under
**Configuration → Application settings** of the Web App (or via
``az webapp config appsettings set``). They are injected as
environment variables at runtime.

Required
--------

``DJANGO_SETTINGS_MODULE``
    Must be ``config.settings.production``.

``DJANGO_SECRET_KEY``
    A long random string used by Django for cryptographic signing.

``SCM_DO_BUILD_DURING_DEPLOYMENT``
    Set to ``1`` so Oryx installs Python dependencies during
    deployment.

``CUSTOM_REQUIREMENTSTXT_PATH``
    Set to ``requirements/production.txt`` to have the App Service
    Oryx build step install the production dependencies during
    deployment.

``POST_BUILD_COMMAND``
    Set to ``python manage.py migrate`` to have the App Service
    Oryx build step run database migrations after deployment.

Database
--------

Either provide an Azure PostgreSQL connection string (preferred when
using the Azure PostgreSQL + App Service integration) or a generic
database URL:

``AZURE_POSTGRESQL_CONNECTIONSTRING``
    libpq keyword/value string, for example
    ``dbname=rundata host=<server>.postgres.database.azure.com user=<user> password=<password>``.
    When this variable is set, it takes precedence over
    ``DATABASE_URL``.

``DATABASE_URL``
    Fallback in the form
    ``postgres://<user>:<password>@<host>:5432/<dbname>``.

``CONN_MAX_AGE``
    Optional, defaults to ``60`` seconds.

Hostnames and HTTPS
-------------------

``WEBSITE_HOSTNAME``
    Automatically provided by App Service (for example
    ``<your-app-name>.azurewebsites.net``). No action required; the
    production settings read it to populate ``ALLOWED_HOSTS`` and
    ``CSRF_TRUSTED_ORIGINS``.

``CANONICAL_DOMAIN``
    Apex domain used for 301 redirects from ``www`` and the
    ``*.azurewebsites.net`` hostname. Defaults to ``rundata.info``;
    override it when deploying your own fork (for example
    ``example.com``).

``DJANGO_ALLOWED_HOSTS``
    Comma-separated list of additional hostnames to allow.

``DJANGO_SECURE_SSL_REDIRECT``
    Defaults to ``true``. Keep it enabled once a valid certificate is
    bound to your custom domain.

``DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS``
    Optional override; defaults to ``true``.

``DJANGO_SECURE_HSTS_PRELOAD``
    Optional override; defaults to ``true``.

``DJANGO_SECURE_CONTENT_TYPE_NOSNIFF``
    Optional override; defaults to ``true``.

Optional integrations
---------------------

``AZURE_BLOB_BASE_URL``
    Set to ``https://files.rundata.info/sveriges_runinskrifter``. This is the public URL of the Azure Blob Storage container that serves runic inscription images.
    In the future, you can set up your own container and provide its URL here.

``MODEL_KEY``
    Set to a non-empty value to enable the AI features. Store this Azure
    Foundry API key only in App Service configuration; never commit it.

``MODEL_ENDPOINT``
    OpenAI-compatible Azure Foundry v1 endpoint, including ``/openai/v1``.
    For example,
    ``https://<resource>.services.ai.azure.com/openai/v1``.

``MODEL_NAME``
    Deployment name to call. The default is ``gpt-6-luna``. You can switch to
    another deployment, such as Phi-4, without changing application code as
    long as it supports the OpenAI v1 Chat Completions API. If the deployment
    is in another Foundry resource, update ``MODEL_ENDPOINT`` and ``MODEL_KEY``
    together.

``MODEL_REASONING_EFFORT``
    Optional reasoning effort for models that support it. Leave unset for
    models, such as Phi-4, that do not accept this parameter.

``APPLICATIONINSIGHTS_CONNECTION_STRING``
    Enable Application Insights telemetry when set.

``GTM_CONTAINER_ID``
    Set to the production Google Tag Manager web container ID (``GTM-…``).
    Configure and publish the Google Analytics tag in that container. Leave
    the setting unset or empty to omit the container from the site.

5. First deployment checklist
=============================

#. Verify the Web App starts under ``PYTHON|3.12`` (Log stream →
   **Log stream** in the portal).
#. If your ``POST_BUILD_COMMAND`` already runs ``python manage.py migrate``,
   do not run migrations manually again. Use **SSH** from the Kudu console
   for ``collectstatic`` (and only run ``migrate`` manually if you did not
   configure it in ``POST_BUILD_COMMAND``)::

    $ python manage.py collectstatic --noinput
    $ python manage.py migrate  # only if POST_BUILD_COMMAND does not run it

#. Open ``https://<your-app-name>.azurewebsites.net`` and confirm
   the site responds.
#. Configure your custom domain and TLS binding, then set
   ``CANONICAL_DOMAIN`` accordingly so the ``www`` and
   ``azurewebsites.net`` hostnames redirect to the apex domain.

.. seealso::

    * :doc:`install` for a generic installation guide.
    * :doc:`docker` for running the project locally in containers
      before deploying.
