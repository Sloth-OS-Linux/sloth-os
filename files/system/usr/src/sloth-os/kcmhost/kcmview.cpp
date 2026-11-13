#include "kcmview.h"

#include <KAbstractConfigModule>
#include <KPluginMetaData>
#include <KQuickConfigModule>
#include <KQuickConfigModuleLoader>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QDebug>

// The page row around the page: a Kirigami.ApplicationItem, so the page's header (title, actions, back button)
// and its sub-pages work as in System Settings.
static const char HOST_QML[] = R"QML(
import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.ApplicationItem {
    property QtObject kcm
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.ShowBackButton
    pageStack.defaultColumnWidth: kcm && kcm.columnWidth > 0 ? kcm.columnWidth : Kirigami.Units.gridUnit * 15
    // one column when the page wants the full width or only one page is open; side by side otherwise
    pageStack.columnView.columnResizeMode: pageStack.items.length > 0
        && (pageStack.items[0].Kirigami.ColumnView.fillWidth || pageStack.items.filter(i => i.visible).length === 1)
        ? Kirigami.ColumnView.SingleColumn : Kirigami.ColumnView.FixedColumns
}
)QML";

KcmView::KcmView(QQuickItem *parent)
    : QQuickItem(parent)
{
}

KcmView::~KcmView()
{
    unload();
}

void KcmView::setModule(const QString &module)
{
    if (module == m_module)
        return;
    m_module = module;
    Q_EMIT moduleChanged();
    if (isComponentComplete())
        load();
}

void KcmView::setArguments(const QStringList &arguments)
{
    if (arguments == m_arguments)
        return;
    m_arguments = arguments;
    Q_EMIT moduleChanged();
}

void KcmView::componentComplete()
{
    QQuickItem::componentComplete();
    load();
}

void KcmView::fail(const QString &message)
{
    m_error = message.isEmpty() ? QStringLiteral("unknown error") : message;
    qWarning().noquote() << "kcmhost:" << m_module << m_error;
    Q_EMIT stateChanged();
}

void KcmView::unload()
{
    if (m_host) {
        m_host->setParentItem(nullptr);
        m_host->deleteLater();
    }
    if (m_kcm)
        m_kcm->deleteLater();
    m_host = nullptr;
    m_pageRow = nullptr;
    m_kcm = nullptr;
}

void KcmView::load()
{
    unload();
    m_error.clear();
    if (m_module.isEmpty())
        return;
    QQmlEngine *engine = qmlEngine(this);
    if (!engine)
        return fail(QStringLiteral("no QML engine"));

    // System Settings' pages, and "About this System" (kcm_about-distro), which lives one folder up
    KPluginMetaData md = KPluginMetaData::findPluginById(QStringLiteral("plasma/kcms/systemsettings"), m_module);
    if (!md.isValid())
        md = KPluginMetaData::findPluginById(QStringLiteral("plasma/kcms"), m_module);
    if (!md.isValid())
        return fail(QStringLiteral("no such settings page"));

    QVariantList args;
    for (const QString &a : std::as_const(m_arguments))
        args << a;
    // the application's own engine (not owned here): the page lives in this scene
    const std::shared_ptr<QQmlEngine> shared(engine, [](QQmlEngine *) {});
    const auto result = KQuickConfigModuleLoader::loadModule(md, this, args, shared);
    if (!result)
        return fail(result.errorString);
    m_kcm = result.plugin;

    // mainUi() first: it sets up the page's QML, which the page's load() uses
    QQuickItem *mainUi = m_kcm->mainUi();
    if (!mainUi)
        return fail(QStringLiteral("the page did not load: ") + m_kcm->errorString());

    QQmlComponent component(engine);
    // a local URL: loaded at once, not asynchronously
    component.setData(HOST_QML, QUrl(QStringLiteral("qrc:/org/slothos/kcmhost/KcmHost.qml")));
    QObject *object = component.create(qmlContext(this));
    m_host = qobject_cast<QQuickItem *>(object);
    if (!m_host) {
        delete object;
        return fail(QStringLiteral("the page row did not load: ") + component.errorString());
    }
    m_host->setParentItem(this);
    m_host->setProperty("kcm", QVariant::fromValue(static_cast<QObject *>(m_kcm.data())));
    layoutHost();

    m_pageRow = m_host->property("pageStack").value<QQuickItem *>();
    if (!m_pageRow)
        return fail(QStringLiteral("no page row"));
    m_pageRow->setProperty("initialPage", QVariant::fromValue(mainUi));
    // sub-pages the page already has (opened with arguments)
    for (int i = 0; i < m_kcm->depth() - 1; ++i) {
        QMetaObject::invokeMethod(m_pageRow, "push", Qt::DirectConnection,
                                  Q_ARG(QVariant, QVariant::fromValue(m_kcm->subPage(i))), Q_ARG(QVariant, QVariant()));
    }
    connect(m_kcm, &KQuickConfigModule::pagePushed, this, [this](QQuickItem *page) {
        if (m_pageRow)
            QMetaObject::invokeMethod(m_pageRow, "push", Qt::DirectConnection, Q_ARG(QVariant, QVariant::fromValue(page)),
                                      Q_ARG(QVariant, QVariant()));
    });
    connect(m_kcm, &KQuickConfigModule::pageRemoved, this, [this]() {
        if (m_pageRow)
            QMetaObject::invokeMethod(m_pageRow, "pop", Qt::DirectConnection, Q_ARG(QVariant, QVariant()));
    });
    connect(m_kcm, &KQuickConfigModule::currentIndexChanged, this, [this]() {
        if (m_pageRow && m_kcm)
            m_pageRow->setProperty("currentIndex", m_kcm->currentIndex());
    });
    connect(m_pageRow, SIGNAL(currentIndexChanged()), this, SLOT(syncCurrentIndex()));

    for (auto signal : {&KAbstractConfigModule::needsSaveChanged, &KAbstractConfigModule::representsDefaultsChanged,
                        &KAbstractConfigModule::buttonsChanged, &KAbstractConfigModule::supportsInstantApplyChanged}) {
        connect(m_kcm, signal, this, &KcmView::stateChanged);
    }
    m_kcm->load();
    m_kcm->setNeedsSave(false);
    Q_EMIT stateChanged();
}

void KcmView::syncCurrentIndex()
{
    if (m_kcm && m_pageRow)
        m_kcm->setCurrentIndex(m_pageRow->property("currentIndex").toInt());
}

void KcmView::layoutHost()
{
    if (m_host) {
        m_host->setPosition(QPointF(0, 0));
        m_host->setSize(size());
    }
}

void KcmView::geometryChange(const QRectF &newGeometry, const QRectF &oldGeometry)
{
    QQuickItem::geometryChange(newGeometry, oldGeometry);
    layoutHost();
}

bool KcmView::loaded() const
{
    return m_kcm && m_host && m_error.isEmpty();
}

QString KcmView::title() const
{
    return m_kcm ? m_kcm->name() : QString();
}

bool KcmView::needsSave() const
{
    return m_kcm && m_kcm->needsSave();
}

bool KcmView::representsDefaults() const
{
    return m_kcm && m_kcm->representsDefaults();
}

bool KcmView::instantApply() const
{
    return m_kcm && m_kcm->supportsInstantApply();
}

bool KcmView::hasApply() const
{
    return m_kcm && (m_kcm->buttons() & KAbstractConfigModule::Apply);
}

bool KcmView::hasDefaults() const
{
    return m_kcm && (m_kcm->buttons() & KAbstractConfigModule::Default);
}

void KcmView::save()
{
    if (!m_kcm)
        return;
    m_kcm->save();
    m_kcm->setNeedsSave(false);
    Q_EMIT stateChanged();
}

void KcmView::reset()
{
    if (!m_kcm)
        return;
    m_kcm->load();
    m_kcm->setNeedsSave(false);
    Q_EMIT stateChanged();
}

void KcmView::defaults()
{
    if (m_kcm)
        m_kcm->defaults();
    Q_EMIT stateChanged();
}
